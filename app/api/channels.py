"""Lazo Agent — Channel Management Routes"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_operator
from app.models import Channel

router = APIRouter()


@router.get("")
async def list_channels(
    db: AsyncSession = Depends(get_db),
    operator: dict = Depends(get_current_operator),
):
    """List all channels."""
    result = await db.execute(select(Channel).order_by(Channel.name))
    channels = result.scalars().all()

    return {
        "channels": [
            {
                "id": str(c.id),
                "name": c.name,
                "slug": c.slug,
                "channel_type": c.channel_type.value,
                "is_active": c.is_active,
                "description": c.description,
            }
            for c in channels
        ]
    }


@router.post("/{channel_id}/toggle")
async def toggle_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    operator: dict = Depends(get_current_operator),
):
    """Enable/disable a channel."""
    if operator.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    channel.is_active = not channel.is_active
    await db.commit()

    return {"id": str(channel.id), "is_active": channel.is_active}
