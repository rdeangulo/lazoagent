"""
Lazo Agent — Analytics Service

Provides metrics and insights for the analytics dashboard:
- Conversation volume and trends
- Response times and resolution rates
- Channel performance
- Inbox SLA compliance
- Agent activity
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Computes analytics metrics from conversation data."""

    async def get_overview_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """Get high-level KPI metrics."""
        from app.core.database import get_db_context
        from app.models import Escalation, InboxItem, Message, Thread
        from app.models.inbox import InboxStatus
        from app.models.thread import ThreadStatus
        from sqlalchemy import func, select

        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        async with get_db_context() as db:
            # Total conversations
            total_threads = (await db.execute(
                select(func.count()).select_from(Thread).where(
                    Thread.created_at.between(start_date, end_date)
                )
            )).scalar()

            # Resolved conversations
            resolved_threads = (await db.execute(
                select(func.count()).select_from(Thread).where(
                    Thread.created_at.between(start_date, end_date),
                    Thread.status == ThreadStatus.CLOSED,
                )
            )).scalar()

            # Escalation rate
            total_escalations = (await db.execute(
                select(func.count()).select_from(Escalation).where(
                    Escalation.created_at.between(start_date, end_date)
                )
            )).scalar()

            # Inbox metrics
            inbox_pending = (await db.execute(
                select(func.count()).select_from(InboxItem).where(
                    InboxItem.status.in_([InboxStatus.NEW, InboxStatus.IN_PROGRESS])
                )
            )).scalar()

            # Total messages
            total_messages = (await db.execute(
                select(func.count()).select_from(Message).where(
                    Message.created_at.between(start_date, end_date)
                )
            )).scalar()

            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "conversations": {
                    "total": total_threads,
                    "resolved": resolved_threads,
                    "resolution_rate": round(
                        (resolved_threads / max(total_threads, 1)) * 100, 1
                    ),
                },
                "escalations": {
                    "total": total_escalations,
                    "escalation_rate": round(
                        (total_escalations / max(total_threads, 1)) * 100, 1
                    ),
                },
                "inbox": {
                    "pending": inbox_pending,
                },
                "messages": {
                    "total": total_messages,
                },
            }

    async def get_channel_breakdown(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get conversation counts by channel."""
        from app.core.database import get_db_context
        from app.models import Channel, Thread
        from sqlalchemy import func, select

        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        async with get_db_context() as db:
            stmt = (
                select(
                    Channel.name,
                    Channel.channel_type,
                    func.count(Thread.id).label("count"),
                )
                .join(Thread, Thread.channel_id == Channel.id)
                .where(Thread.created_at.between(start_date, end_date))
                .group_by(Channel.name, Channel.channel_type)
                .order_by(func.count(Thread.id).desc())
            )

            result = await db.execute(stmt)
            rows = result.all()

            return [
                {
                    "channel": row.name,
                    "type": row.channel_type.value if hasattr(row.channel_type, 'value') else row.channel_type,
                    "conversations": row.count,
                }
                for row in rows
            ]

    async def get_daily_volume(
        self,
        days: int = 30,
    ) -> list[dict]:
        """Get daily conversation volume for charting."""
        from app.core.database import get_db_context
        from app.models import Thread
        from sqlalchemy import cast, func, select, Date

        start = datetime.now(timezone.utc) - timedelta(days=days)

        async with get_db_context() as db:
            stmt = (
                select(
                    cast(Thread.created_at, Date).label("date"),
                    func.count(Thread.id).label("count"),
                )
                .where(Thread.created_at >= start)
                .group_by(cast(Thread.created_at, Date))
                .order_by(cast(Thread.created_at, Date))
            )

            result = await db.execute(stmt)
            return [
                {"date": row.date.isoformat(), "conversations": row.count}
                for row in result.all()
            ]


# Singleton
analytics_service = AnalyticsService()
