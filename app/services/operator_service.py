"""
Lazo Agent — Operator Service

Manages operator lifecycle: login/logout, status tracking,
stale session cleanup, and inbox processing on login.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class OperatorService:
    """Manages operator state and session lifecycle."""

    async def login(self, email: str, password: str) -> dict:
        """Authenticate operator and set them online."""
        from app.core.database import get_db_context
        from app.core.security import create_access_token, verify_password
        from app.models import Operator, OperatorLog
        from app.models.operator import OperatorStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            stmt = select(Operator).where(Operator.email == email)
            result = await db.execute(stmt)
            operator = result.scalar_one_or_none()

            if not operator or not verify_password(password, operator.password_hash):
                raise ValueError("Invalid email or password")

            # Update status
            operator.status = OperatorStatus.ONLINE
            operator.last_login = datetime.now(timezone.utc)
            operator.last_activity = datetime.now(timezone.utc)

            # Log event
            log = OperatorLog(
                operator_id=operator.id,
                event="login",
            )
            db.add(log)

            # Generate JWT
            token = create_access_token({
                "sub": str(operator.id),
                "email": operator.email,
                "name": operator.name,
                "role": operator.role.value,
            })

            return {
                "access_token": token,
                "operator": {
                    "id": str(operator.id),
                    "name": operator.name,
                    "email": operator.email,
                    "role": operator.role.value,
                    "status": operator.status.value,
                },
            }

    async def logout(self, operator_id: str):
        """Set operator offline."""
        from app.core.database import get_db_context
        from app.models import Operator, OperatorLog
        from app.models.operator import OperatorStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            stmt = select(Operator).where(Operator.id == operator_id)
            result = await db.execute(stmt)
            operator = result.scalar_one_or_none()

            if not operator:
                raise NotFoundError("Operator", operator_id)

            operator.status = OperatorStatus.OFFLINE
            db.add(OperatorLog(operator_id=operator.id, event="logout"))

    async def update_status(self, operator_id: str, status: str):
        """Update operator status (online/offline/away)."""
        from app.core.database import get_db_context
        from app.models import Operator
        from app.models.operator import OperatorStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            stmt = select(Operator).where(Operator.id == operator_id)
            result = await db.execute(stmt)
            operator = result.scalar_one_or_none()

            if not operator:
                raise NotFoundError("Operator", operator_id)

            operator.status = OperatorStatus(status)
            operator.last_activity = datetime.now(timezone.utc)

    async def get_online_count(self) -> int:
        """Count currently online operators."""
        from app.core.database import get_db_context
        from app.models import Operator
        from app.models.operator import OperatorStatus
        from sqlalchemy import func, select

        async with get_db_context() as db:
            result = await db.execute(
                select(func.count()).select_from(Operator).where(
                    Operator.status == OperatorStatus.ONLINE
                )
            )
            return result.scalar()

    async def cleanup_stale_operators(self, timeout_minutes: int = 30):
        """Mark operators as offline if no activity within timeout."""
        from app.core.database import get_db_context
        from app.models import Operator
        from app.models.operator import OperatorStatus
        from datetime import timedelta
        from sqlalchemy import select, update

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

        async with get_db_context() as db:
            stmt = (
                update(Operator)
                .where(
                    Operator.status == OperatorStatus.ONLINE,
                    Operator.last_activity < cutoff,
                )
                .values(status=OperatorStatus.OFFLINE)
            )
            result = await db.execute(stmt)
            count = result.rowcount

            if count:
                logger.info("Marked %d stale operators as offline", count)


# Singleton
operator_service = OperatorService()
