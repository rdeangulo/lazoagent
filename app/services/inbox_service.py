"""
Lazo Agent — Inbox Service

Manages the offline inbox where conversations are queued
when no agents are available. Captures contact data and
tracks SLA compliance.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from app.config import settings

logger = logging.getLogger(__name__)


class InboxService:
    """Manages inbox items for offline follow-up."""

    async def create_inbox_item(
        self,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
        contact_name: Optional[str] = None,
        note: Optional[str] = None,
        thread_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> dict:
        """Create a new inbox item with captured contact info."""
        from app.core.database import get_db_context
        from app.models import InboxItem
        from app.models.inbox import InboxStatus

        sla_deadline = datetime.now(timezone.utc) + timedelta(
            minutes=settings.INBOX_SLA_MINUTES
        )

        async with get_db_context() as db:
            item = InboxItem(
                thread_id=thread_id,
                customer_id=customer_id,
                channel_id=channel_id,
                status=InboxStatus.NEW,
                contact_email=contact_email,
                contact_phone=contact_phone,
                contact_name=contact_name,
                customer_message=note,
                sla_deadline=sla_deadline,
            )
            db.add(item)
            await db.flush()

            reference_id = str(item.id)[:8].upper()

            logger.info(
                "Created inbox item %s (contact: %s, SLA: %s)",
                reference_id,
                contact_email or contact_phone,
                sla_deadline,
            )

            return {
                "inbox_item_id": str(item.id),
                "reference_id": reference_id,
                "sla_hours": settings.INBOX_SLA_MINUTES / 60,
                "sla_deadline": sla_deadline.isoformat(),
            }

    async def get_inbox_items(
        self,
        status: Optional[str] = None,
        operator_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Get inbox items with optional filtering."""
        from app.core.database import get_db_context
        from app.models import InboxItem
        from app.models.inbox import InboxStatus
        from sqlalchemy import func, select

        async with get_db_context() as db:
            stmt = select(InboxItem).order_by(InboxItem.sla_deadline.asc())

            if status:
                stmt = stmt.where(InboxItem.status == InboxStatus(status))
            if operator_id:
                stmt = stmt.where(InboxItem.assigned_operator_id == operator_id)

            # Count total
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await db.execute(count_stmt)).scalar()

            # Paginate
            stmt = stmt.offset(offset).limit(limit)
            result = await db.execute(stmt)
            items = result.scalars().all()

            return {
                "items": [self._format_item(item) for item in items],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    async def assign_inbox_item(
        self,
        inbox_item_id: str,
        operator_id: str,
    ) -> dict:
        """Assign an inbox item to an operator."""
        from app.core.database import get_db_context
        from app.models import InboxItem
        from app.models.inbox import InboxStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            stmt = select(InboxItem).where(InboxItem.id == inbox_item_id)
            result = await db.execute(stmt)
            item = result.scalar_one_or_none()

            if not item:
                raise ValueError(f"Inbox item {inbox_item_id} not found")

            item.assigned_operator_id = operator_id
            item.status = InboxStatus.IN_PROGRESS
            if not item.first_response_at:
                item.first_response_at = datetime.now(timezone.utc)

            return self._format_item(item)

    async def resolve_inbox_item(
        self,
        inbox_item_id: str,
        resolution_note: str,
    ) -> dict:
        """Mark an inbox item as resolved."""
        from app.core.database import get_db_context
        from app.models import InboxItem
        from app.models.inbox import InboxStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            stmt = select(InboxItem).where(InboxItem.id == inbox_item_id)
            result = await db.execute(stmt)
            item = result.scalar_one_or_none()

            if not item:
                raise ValueError(f"Inbox item {inbox_item_id} not found")

            item.status = InboxStatus.RESOLVED
            item.resolved_at = datetime.now(timezone.utc)
            item.resolution_note = resolution_note

            return self._format_item(item)

    async def get_sla_metrics(self) -> dict:
        """Get SLA compliance metrics."""
        from app.core.database import get_db_context
        from app.models import InboxItem
        from app.models.inbox import InboxStatus
        from sqlalchemy import func, select

        async with get_db_context() as db:
            now = datetime.now(timezone.utc)

            # Total items
            total = (await db.execute(
                select(func.count()).select_from(InboxItem)
            )).scalar()

            # Breached SLA (new + sla_deadline passed)
            breached = (await db.execute(
                select(func.count()).select_from(InboxItem).where(
                    InboxItem.status == InboxStatus.NEW,
                    InboxItem.sla_deadline < now,
                )
            )).scalar()

            # Resolved
            resolved = (await db.execute(
                select(func.count()).select_from(InboxItem).where(
                    InboxItem.status == InboxStatus.RESOLVED,
                )
            )).scalar()

            # Pending
            pending = (await db.execute(
                select(func.count()).select_from(InboxItem).where(
                    InboxItem.status.in_([InboxStatus.NEW, InboxStatus.IN_PROGRESS]),
                )
            )).scalar()

            return {
                "total": total,
                "pending": pending,
                "resolved": resolved,
                "sla_breached": breached,
                "sla_compliance_rate": (
                    round((1 - breached / max(total, 1)) * 100, 1)
                ),
            }

    def _format_item(self, item) -> dict:
        return {
            "id": str(item.id),
            "thread_id": str(item.thread_id) if item.thread_id else None,
            "status": item.status.value,
            "contact_email": item.contact_email,
            "contact_phone": item.contact_phone,
            "contact_name": item.contact_name,
            "subject": item.subject,
            "conversation_summary": item.conversation_summary,
            "customer_message": item.customer_message,
            "sla_deadline": item.sla_deadline.isoformat() if item.sla_deadline else None,
            "first_response_at": item.first_response_at.isoformat() if item.first_response_at else None,
            "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
            "resolution_note": item.resolution_note,
            "created_at": item.created_at.isoformat(),
            "assigned_operator_id": str(item.assigned_operator_id) if item.assigned_operator_id else None,
        }


# Singleton
inbox_service = InboxService()
