"""Lazo Agent — B2Chat Integration Routes"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_admin

router = APIRouter()


@router.get("/health")
async def b2chat_health(admin: dict = Depends(get_current_admin)):
    """Check B2Chat API connectivity."""
    from app.services.b2chat_service import b2chat_service

    reachable = await b2chat_service.health_check()
    if not reachable:
        return {"status": "unreachable", "message": "Cannot connect to B2Chat API"}

    try:
        await b2chat_service._authenticate()
        return {"status": "connected", "message": "B2Chat API authenticated"}
    except Exception as e:
        return {"status": "auth_failed", "message": str(e)}


@router.post("/sync")
async def sync_knowledge(
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    messaging_provider: Optional[str] = Query(None, description="whatsapp|facebook|telegram|livechat"),
    max_chats: int = Query(5000, le=50000),
    admin: dict = Depends(get_current_admin),
):
    """Trigger B2Chat → Knowledge Base sync.

    Pulls historical conversations from B2Chat, processes them through
    the LLM synthesis pipeline, and stores as knowledge documents.
    """
    if not admin.get("sub"):
        raise HTTPException(status_code=403, detail="Admin access required")

    from app.services.b2chat_ingestion import ingestion_pipeline

    try:
        result = await ingestion_pipeline.run(
            date_from=date_from,
            date_to=date_to,
            messaging_provider=messaging_provider,
            max_chats=max_chats,
            uploaded_by_id=admin.get("sub"),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/chats/preview")
async def preview_chats(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    messaging_provider: Optional[str] = Query(None),
    limit: int = Query(10, le=100),
    admin: dict = Depends(get_current_admin),
):
    """Preview B2Chat conversations before syncing.

    Returns a sample of chats so you can verify data quality before
    running the full ingestion pipeline.
    """
    from app.services.b2chat_service import b2chat_service, B2ChatService

    chats = await b2chat_service.export_chats(
        date_from=date_from,
        date_to=date_to,
        messaging_provider=messaging_provider,
        limit=limit,
    )

    return {
        "total_returned": len(chats),
        "chats": [
            {
                "chat_id": chat.get("id") or chat.get("chat_id"),
                "channel": chat.get("messaging_provider") or chat.get("channel"),
                "contact": chat.get("contact", {}).get("fullname", "Unknown"),
                "message_count": len(B2ChatService.extract_messages_from_chat(chat)),
                "preview": B2ChatService.format_chat_as_text(chat)[:500],
            }
            for chat in chats
        ],
    }
