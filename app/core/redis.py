"""
Lazo Agent — Redis Connection Management

Provides async Redis client for caching, pub/sub, and session management.
Gracefully degrades if Redis is unavailable (local-only mode).
"""

from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None
_redis_available: bool = False


async def get_redis() -> Optional[aioredis.Redis]:
    """Get the Redis client. Returns None if Redis is unavailable."""
    global _redis_client, _redis_available

    if _redis_client is not None:
        return _redis_client if _redis_available else None

    try:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            retry_on_timeout=True,
        )
        await _redis_client.ping()
        _redis_available = True
        logger.info("Redis connected: %s", settings.REDIS_URL)
        return _redis_client
    except Exception as e:
        logger.warning("Redis unavailable, running in local-only mode: %s", e)
        _redis_available = False
        return None


async def close_redis():
    """Gracefully close the Redis connection."""
    global _redis_client, _redis_available
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        _redis_available = False
        logger.info("Redis connection closed")


def is_redis_available() -> bool:
    """Check if Redis is currently available."""
    return _redis_available
