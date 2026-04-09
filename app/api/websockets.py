"""Lazo Agent — WebSocket Routes"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/{thread_id}")
async def thread_websocket(websocket: WebSocket, thread_id: str):
    """WebSocket connection for a specific thread.

    Used by both the customer widget and the CRM operator view
    to receive real-time messages.
    """
    await ws_manager.connect_thread(thread_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle pong responses (keepalive)
            if data.get("type") == "pong":
                continue
            # Forward messages to thread (for operator replies via WS)
            if data.get("type") == "message":
                await ws_manager.broadcast_to_thread(thread_id, data)
    except WebSocketDisconnect:
        await ws_manager.disconnect_thread(thread_id, websocket)


@router.websocket("/ws/global")
async def global_websocket(websocket: WebSocket):
    """Global CRM WebSocket — operators see all events.

    Events: new threads, escalations, inbox items, status changes.
    """
    # TODO: Validate operator JWT from query params or first message
    await ws_manager.connect_global(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "pong":
                continue
    except WebSocketDisconnect:
        await ws_manager.disconnect_global(websocket)
