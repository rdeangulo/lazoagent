"""Lazo Agent — Thread & Message Routes"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.bridge import process_message
from app.core.database import get_db
from app.core.security import get_current_operator, get_optional_operator
from app.core.websocket_manager import ws_manager
from app.models import Message, Thread
from app.models.message import SenderType
from app.models.thread import ThreadStatus
from app.schemas.thread import MessageCreate

router = APIRouter()


@router.get("")
async def list_threads(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    operator: dict = Depends(get_current_operator),
):
    """List threads with optional status filter."""
    stmt = select(Thread).order_by(Thread.updated_at.desc())

    if status:
        stmt = stmt.where(Thread.status == ThreadStatus(status))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar()

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    threads = result.scalars().all()

    return {
        "threads": [_format_thread(t) for t in threads],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{thread_id}")
async def get_thread(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    operator: dict = Depends(get_optional_operator),
):
    """Get a single thread with messages."""
    stmt = select(Thread).where(Thread.id == thread_id)
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    return _format_thread(thread)


@router.post("/{thread_id}/messages")
async def create_message(
    thread_id: str,
    request: MessageCreate,
    db: AsyncSession = Depends(get_db),
    operator: dict = Depends(get_optional_operator),
):
    """Create a message in a thread.

    - If sender_type is 'customer': processes through AI agent
    - If sender_type is 'operator': sends directly (human agent reply)
    """
    # Get or create thread
    stmt = select(Thread).where(Thread.id == thread_id)
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Save the incoming message
    message = Message(
        thread_id=thread_id,
        sender_type=SenderType(request.sender_type),
        content=request.content,
        content_type=request.content_type,
        media_url=request.media_url,
        operator_id=operator.get("sub") if operator and request.sender_type == "operator" else None,
    )
    db.add(message)
    await db.commit()

    # Broadcast to WebSocket
    await ws_manager.broadcast_to_thread(thread_id, {
        "type": "message",
        "sender_type": request.sender_type,
        "content": request.content,
        "thread_id": thread_id,
    })

    # If customer message and thread is active (AI handling), process through agent
    if request.sender_type == "customer" and thread.status == ThreadStatus.ACTIVE:
        ai_result = await process_message(
            message=request.content,
            thread_id=thread_id,
            channel=thread.channel.slug if thread.channel else "web_chat",
            language=thread.language,
            customer_id=str(thread.customer_id) if thread.customer_id else None,
            customer_name=thread.customer.name if thread.customer else None,
            customer_email=thread.customer.email if thread.customer else None,
        )

        # Save AI response
        if ai_result.get("response"):
            ai_message = Message(
                thread_id=thread_id,
                sender_type=SenderType.ASSISTANT,
                content=ai_result["response"],
            )
            db.add(ai_message)
            await db.commit()

            # Broadcast AI response
            await ws_manager.broadcast_to_thread(thread_id, {
                "type": "message",
                "sender_type": "assistant",
                "content": ai_result["response"],
                "thread_id": thread_id,
            })

        # Handle auto-escalation
        if ai_result.get("should_escalate"):
            from app.services.escalation_service import escalation_service
            await escalation_service.escalate(
                thread_id=thread_id,
                reason="Auto-escalation: AI agent error",
                priority="high",
            )

        return {
            "message_id": str(message.id),
            "ai_response": ai_result.get("response"),
            "escalated": ai_result.get("should_escalate", False),
        }

    return {"message_id": str(message.id)}


@router.post("/{thread_id}/take")
async def take_thread(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    operator: dict = Depends(get_current_operator),
):
    """Operator takes over a thread (from escalated/inbox status)."""
    stmt = select(Thread).where(Thread.id == thread_id)
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread.status = ThreadStatus.TAKEN
    thread.operator_id = operator["sub"]
    await db.commit()

    await ws_manager.broadcast_global({
        "type": "thread_taken",
        "thread_id": thread_id,
        "operator_id": operator["sub"],
        "operator_name": operator.get("name"),
    })

    return {"status": "taken", "operator_id": operator["sub"]}


@router.post("/{thread_id}/close")
async def close_thread(
    thread_id: str,
    reason: str = "resolved",
    db: AsyncSession = Depends(get_db),
    operator: dict = Depends(get_current_operator),
):
    """Close a thread."""
    from datetime import datetime, timezone

    stmt = select(Thread).where(Thread.id == thread_id)
    result = await db.execute(stmt)
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    thread.status = ThreadStatus.CLOSED
    thread.closed_reason = reason
    thread.closed_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "closed"}


def _format_thread(thread: Thread) -> dict:
    return {
        "id": str(thread.id),
        "status": thread.status.value,
        "channel_id": str(thread.channel_id) if thread.channel_id else None,
        "customer_id": str(thread.customer_id) if thread.customer_id else None,
        "operator_id": str(thread.operator_id) if thread.operator_id else None,
        "subject": thread.subject,
        "language": thread.language,
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
        "messages": [
            {
                "id": str(m.id),
                "thread_id": str(m.thread_id),
                "sender_type": m.sender_type.value,
                "content": m.content,
                "content_type": m.content_type.value,
                "created_at": m.created_at.isoformat(),
            }
            for m in (thread.messages or [])
        ],
    }
