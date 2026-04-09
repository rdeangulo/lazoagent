"""Lazo Agent — Health Check Routes"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("")
async def health():
    """Basic health check."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }


@router.get("/detailed")
async def detailed_health():
    """Detailed health check including database and Redis status."""
    checks = {
        "app": "healthy",
        "database": "unknown",
        "redis": "unknown",
    }

    # Check database
    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {e}"

    # Check Redis
    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        if redis:
            await redis.ping()
            checks["redis"] = "healthy"
        else:
            checks["redis"] = "unavailable (local-only mode)"
    except Exception as e:
        checks["redis"] = f"unhealthy: {e}"

    overall = "healthy" if all(
        v in ("healthy", "unavailable (local-only mode)")
        for v in checks.values()
    ) else "degraded"

    return {"status": overall, "checks": checks}
