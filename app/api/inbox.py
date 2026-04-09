"""Lazo Agent — Inbox Routes"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_operator
from app.schemas.inbox import AssignInboxRequest, ResolveInboxRequest
from app.services.inbox_service import inbox_service

router = APIRouter()


@router.get("")
async def list_inbox_items(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    operator: dict = Depends(get_current_operator),
):
    """List inbox items (pending follow-ups)."""
    return await inbox_service.get_inbox_items(
        status=status, limit=limit, offset=offset,
    )


@router.post("/{item_id}/assign")
async def assign_inbox_item(
    item_id: str,
    request: AssignInboxRequest,
    operator: dict = Depends(get_current_operator),
):
    """Assign an inbox item to an operator."""
    return await inbox_service.assign_inbox_item(item_id, request.operator_id)


@router.post("/{item_id}/resolve")
async def resolve_inbox_item(
    item_id: str,
    request: ResolveInboxRequest,
    operator: dict = Depends(get_current_operator),
):
    """Mark an inbox item as resolved."""
    return await inbox_service.resolve_inbox_item(item_id, request.resolution_note)


@router.get("/metrics")
async def inbox_metrics(operator: dict = Depends(get_current_operator)):
    """Get inbox SLA metrics."""
    return await inbox_service.get_sla_metrics()
