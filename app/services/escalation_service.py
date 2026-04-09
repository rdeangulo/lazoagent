"""
Lazo Agent — Escalation Service

Handles the escalation flow:
1. AI determines escalation is needed
2. Check if any operator is online
3. If yes → assign to operator, route live via WebSocket
4. If no → create inbox item, capture contact info for follow-up
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from app.config import settings
from app.core.exceptions import EscalationError

logger = logging.getLogger(__name__)


class EscalationService:
    """Manages escalation logic and inbox routing."""

    async def escalate(
        self,
        reason: str,
        priority: str = "normal",
        conversation_summary: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> dict:
        """Escalate a conversation — routes to agent or inbox.

        Returns:
            dict with:
                - agent_available: bool
                - escalation_id: str (if agent available)
                - inbox_item_id: str (if no agent)
        """
        # Check for online operators
        online_operators = await self._get_online_operators()

        if online_operators:
            return await self._escalate_to_agent(
                thread_id=thread_id,
                operator=online_operators[0],  # Simplest: assign to first available
                reason=reason,
                priority=priority,
                conversation_summary=conversation_summary,
            )
        else:
            return await self._escalate_to_inbox(
                thread_id=thread_id,
                reason=reason,
                priority=priority,
                conversation_summary=conversation_summary,
            )

    async def _escalate_to_agent(
        self,
        thread_id: Optional[str],
        operator: dict,
        reason: str,
        priority: str,
        conversation_summary: Optional[str],
    ) -> dict:
        """Route escalation to an online operator."""
        from app.core.database import get_db_context
        from app.core.websocket_manager import ws_manager
        from app.models import Escalation, Thread
        from app.models.escalation import EscalationPriority, EscalationStatus
        from app.models.thread import ThreadStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            # Update thread status
            if thread_id:
                stmt = select(Thread).where(Thread.id == thread_id)
                result = await db.execute(stmt)
                thread = result.scalar_one_or_none()
                if thread:
                    thread.status = ThreadStatus.ESCALATED
                    thread.escalation_reason = reason
                    thread.escalated_at = datetime.now(timezone.utc)
                    thread.conversation_summary = conversation_summary

            # Create escalation record
            escalation = Escalation(
                thread_id=thread_id,
                assigned_operator_id=operator["id"],
                priority=EscalationPriority(priority),
                status=EscalationStatus.ASSIGNED,
                reason=reason,
                conversation_summary=conversation_summary,
            )
            db.add(escalation)
            await db.flush()

            escalation_id = str(escalation.id)

        # Notify via WebSocket
        await ws_manager.broadcast_global({
            "type": "escalation",
            "thread_id": thread_id,
            "escalation_id": escalation_id,
            "operator_id": str(operator["id"]),
            "reason": reason,
            "priority": priority,
        })

        logger.info(
            "Escalated thread %s to operator %s (priority: %s)",
            thread_id, operator.get("name"), priority,
        )

        return {
            "agent_available": True,
            "escalation_id": escalation_id,
            "operator_name": operator.get("name"),
        }

    async def _escalate_to_inbox(
        self,
        thread_id: Optional[str],
        reason: str,
        priority: str,
        conversation_summary: Optional[str],
    ) -> dict:
        """No agents online — create inbox item for later follow-up."""
        from app.core.database import get_db_context
        from app.models import Escalation, InboxItem, Thread
        from app.models.escalation import EscalationPriority, EscalationStatus
        from app.models.inbox import InboxStatus
        from app.models.thread import ThreadStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            # Update thread status
            if thread_id:
                stmt = select(Thread).where(Thread.id == thread_id)
                result = await db.execute(stmt)
                thread = result.scalar_one_or_none()
                if thread:
                    thread.status = ThreadStatus.INBOX

            # Create escalation with inbox status
            escalation = Escalation(
                thread_id=thread_id,
                priority=EscalationPriority(priority),
                status=EscalationStatus.INBOX,
                reason=reason,
                conversation_summary=conversation_summary,
            )
            db.add(escalation)

            # Create inbox item with SLA
            sla_deadline = datetime.now(timezone.utc) + timedelta(
                minutes=settings.INBOX_SLA_MINUTES
            )
            inbox_item = InboxItem(
                thread_id=thread_id,
                status=InboxStatus.NEW,
                subject=reason,
                conversation_summary=conversation_summary,
                sla_deadline=sla_deadline,
            )
            db.add(inbox_item)
            await db.flush()

            inbox_id = str(inbox_item.id)

        logger.info(
            "No agents online — created inbox item %s for thread %s (SLA: %s)",
            inbox_id, thread_id, sla_deadline,
        )

        return {
            "agent_available": False,
            "inbox_item_id": inbox_id,
            "sla_hours": settings.INBOX_SLA_MINUTES / 60,
        }

    async def _get_online_operators(self) -> list[dict]:
        """Get list of currently online operators."""
        from app.core.database import get_db_context
        from app.models import Operator
        from app.models.operator import OperatorStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            stmt = select(Operator).where(Operator.status == OperatorStatus.ONLINE)
            result = await db.execute(stmt)
            operators = result.scalars().all()

            return [
                {"id": op.id, "name": op.name, "email": op.email}
                for op in operators
            ]

    async def resolve_escalation(
        self,
        escalation_id: str,
        operator_id: str,
        resolution_note: str,
    ) -> dict:
        """Mark an escalation as resolved."""
        from app.core.database import get_db_context
        from app.models import Escalation, Thread
        from app.models.escalation import EscalationStatus
        from app.models.thread import ThreadStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            stmt = select(Escalation).where(Escalation.id == escalation_id)
            result = await db.execute(stmt)
            escalation = result.scalar_one_or_none()

            if not escalation:
                raise EscalationError(f"Escalation {escalation_id} not found")

            escalation.status = EscalationStatus.RESOLVED
            escalation.resolved_at = datetime.now(timezone.utc)
            escalation.resolution_note = resolution_note

            # Close the thread
            if escalation.thread_id:
                stmt = select(Thread).where(Thread.id == escalation.thread_id)
                result = await db.execute(stmt)
                thread = result.scalar_one_or_none()
                if thread:
                    thread.status = ThreadStatus.CLOSED
                    thread.closed_reason = "escalation_resolved"
                    thread.closed_at = datetime.now(timezone.utc)

        return {"status": "resolved", "escalation_id": escalation_id}


# Singleton
escalation_service = EscalationService()
