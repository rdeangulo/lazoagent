"""Lazo Agent — Escalation Routes"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_operator
from app.models import Escalation
from app.models.escalation import EscalationStatus
from app.schemas.escalation import ResolveEscalationRequest
from app.services.escalation_service import escalation_service

router = APIRouter()


@router.get("")
async def list_escalations(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    operator: dict = Depends(get_current_operator),
):
    """List escalations with optional status filter."""
    stmt = select(Escalation).order_by(Escalation.created_at.desc())
    if status:
        stmt = stmt.where(Escalation.status == EscalationStatus(status))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar()
    result = await db.execute(stmt.offset(offset).limit(limit))
    escalations = result.scalars().all()

    return {
        "escalations": [_format(e) for e in escalations],
        "total": total,
    }


@router.post("/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: str,
    request: ResolveEscalationRequest,
    operator: dict = Depends(get_current_operator),
):
    """Resolve an escalation."""
    result = await escalation_service.resolve_escalation(
        escalation_id=escalation_id,
        operator_id=operator["sub"],
        resolution_note=request.resolution_note,
    )
    return result


def _format(e: Escalation) -> dict:
    return {
        "id": str(e.id),
        "thread_id": str(e.thread_id),
        "status": e.status.value,
        "priority": e.priority.value,
        "reason": e.reason,
        "conversation_summary": e.conversation_summary,
        "assigned_operator_id": str(e.assigned_operator_id) if e.assigned_operator_id else None,
        "created_at": e.created_at.isoformat(),
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
    }
