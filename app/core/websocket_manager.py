"""
Lazo Agent — WebSocket Connection Manager

Manages real-time connections for:
- Per-thread connections (customer widget ↔ operator CRM)
- Global CRM feed (all operators see new/escalated threads)
- Redis pub/sub for multi-worker broadcasting

Includes heartbeat, deduplication, and reconnection support.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Optional

from fastapi import WebSocket

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with Redis pub/sub for multi-instance support."""

    def __init__(self):
        self._thread_connections: dict[str, list[WebSocket]] = {}
        self._global_connections: list[WebSocket] = []
        self._seen_messages: dict[str, float] = {}  # msg_uuid -> timestamp
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._pubsub_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background tasks for heartbeat and cleanup."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_stale_messages())
        self._pubsub_task = asyncio.create_task(self._redis_subscriber())

    async def stop(self):
        """Cancel background tasks."""
        for task in [self._heartbeat_task, self._cleanup_task, self._pubsub_task]:
            if task:
                task.cancel()

    # ── Thread Connections ───────────────────────────────────────────────

    async def connect_thread(self, thread_id: str, websocket: WebSocket):
        await websocket.accept()
        self._thread_connections.setdefault(thread_id, []).append(websocket)
        logger.info("WS connected to thread %s (total: %d)", thread_id, len(self._thread_connections[thread_id]))

    async def disconnect_thread(self, thread_id: str, websocket: WebSocket):
        conns = self._thread_connections.get(thread_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._thread_connections.pop(thread_id, None)

    async def broadcast_to_thread(self, thread_id: str, data: dict):
        """Send message to all connections on a thread + publish to Redis."""
        msg_uuid = data.setdefault("uuid", str(uuid.uuid4()))

        if msg_uuid in self._seen_messages:
            return
        self._seen_messages[msg_uuid] = time.time()

        # Local broadcast
        conns = self._thread_connections.get(thread_id, [])
        dead = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            conns.remove(ws)

        # Redis publish for cross-worker delivery
        redis = await get_redis()
        if redis:
            await redis.publish(
                f"thread:{thread_id}",
                json.dumps(data),
            )

    # ── Global CRM Feed ──────────────────────────────────────────────────

    async def connect_global(self, websocket: WebSocket):
        await websocket.accept()
        self._global_connections.append(websocket)
        logger.info("Global CRM WS connected (total: %d)", len(self._global_connections))

    async def disconnect_global(self, websocket: WebSocket):
        if websocket in self._global_connections:
            self._global_connections.remove(websocket)

    async def broadcast_global(self, data: dict):
        """Broadcast to all CRM operator connections."""
        msg_uuid = data.setdefault("uuid", str(uuid.uuid4()))

        if msg_uuid in self._seen_messages:
            return
        self._seen_messages[msg_uuid] = time.time()

        dead = []
        for ws in self._global_connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._global_connections.remove(ws)

        redis = await get_redis()
        if redis:
            await redis.publish("global:crm", json.dumps(data))

    # ── Background Tasks ─────────────────────────────────────────────────

    async def _heartbeat_loop(self):
        """Send ping to all connections every 30 seconds."""
        while True:
            try:
                await asyncio.sleep(30)
                all_ws = list(self._global_connections)
                for conns in self._thread_connections.values():
                    all_ws.extend(conns)
                for ws in all_ws:
                    try:
                        await ws.send_json({"type": "ping"})
                    except Exception:
                        pass
            except asyncio.CancelledError:
                break

    async def _cleanup_stale_messages(self):
        """Remove old message UUIDs every 60 seconds (5min TTL)."""
        while True:
            try:
                await asyncio.sleep(60)
                cutoff = time.time() - 300
                self._seen_messages = {
                    k: v for k, v in self._seen_messages.items() if v > cutoff
                }
            except asyncio.CancelledError:
                break

    async def _redis_subscriber(self):
        """Subscribe to Redis pub/sub for cross-worker messages."""
        try:
            redis = await get_redis()
            if not redis:
                return

            pubsub = redis.pubsub()
            await pubsub.psubscribe("thread:*", "global:crm")

            async for message in pubsub.listen():
                if message["type"] != "pmessage":
                    continue
                try:
                    data = json.loads(message["data"])
                    msg_uuid = data.get("uuid")
                    if msg_uuid and msg_uuid in self._seen_messages:
                        continue
                    if msg_uuid:
                        self._seen_messages[msg_uuid] = time.time()

                    channel = message["channel"]
                    if channel == "global:crm":
                        dead = []
                        for ws in self._global_connections:
                            try:
                                await ws.send_json(data)
                            except Exception:
                                dead.append(ws)
                        for ws in dead:
                            self._global_connections.remove(ws)
                    elif channel.startswith("thread:"):
                        thread_id = channel.split(":", 1)[1]
                        conns = self._thread_connections.get(thread_id, [])
                        dead = []
                        for ws in conns:
                            try:
                                await ws.send_json(data)
                            except Exception:
                                dead.append(ws)
                        for ws in dead:
                            conns.remove(ws)
                except Exception as e:
                    logger.error("Redis pubsub error: %s", e)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Redis subscriber failed: %s", e)


# Singleton instance
ws_manager = ConnectionManager()
