"""Lazo Agent — Analytics Routes"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_operator
from app.services.analytics_service import analytics_service
from app.services.inbox_service import inbox_service

router = APIRouter()


@router.get("/overview")
async def get_overview(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    operator: dict = Depends(get_current_operator),
):
    """Get overview metrics for the analytics dashboard."""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    return await analytics_service.get_overview_metrics(start, end)


@router.get("/channels")
async def get_channel_breakdown(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    operator: dict = Depends(get_current_operator),
):
    """Get conversation breakdown by channel."""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    return await analytics_service.get_channel_breakdown(start, end)


@router.get("/volume")
async def get_daily_volume(
    days: int = Query(30, le=365),
    operator: dict = Depends(get_current_operator),
):
    """Get daily conversation volume for charts."""
    return await analytics_service.get_daily_volume(days)


@router.get("/inbox-sla")
async def get_inbox_sla(operator: dict = Depends(get_current_operator)):
    """Get inbox SLA compliance metrics."""
    return await inbox_service.get_sla_metrics()
