"""
Lazo Agent — Database Connection Management

Async SQLAlchemy engine and session factory with connection pool monitoring.
Uses asyncpg for production-grade async PostgreSQL access.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings

logger = logging.getLogger(__name__)

# ── Engine Configuration ─────────────────────────────────────────────────────

_pool_kwargs = (
    # NullPool for PgBouncer environments (transaction-mode pooling)
    {"poolclass": NullPool}
    if "pgbouncer" in settings.DATABASE_URL.lower()
    else {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_pre_ping": True,
    }
)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    **_pool_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Optional analytics engine (read replica) ────────────────────────────────

analytics_engine = None
AnalyticsSessionLocal = None

if settings.ANALYTICS_DATABASE_URL:
    analytics_engine = create_async_engine(
        settings.ANALYTICS_DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=3,
        pool_pre_ping=True,
    )
    AnalyticsSessionLocal = async_sessionmaker(
        analytics_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# ── Dependency Injection ─────────────────────────────────────────────────────


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_analytics_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields analytics DB session, falls back to main DB."""
    factory = AnalyticsSessionLocal or AsyncSessionLocal
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for use outside of FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Lifecycle ────────────────────────────────────────────────────────────────


async def dispose_engines():
    """Gracefully close all database connections."""
    await engine.dispose()
    if analytics_engine:
        await analytics_engine.dispose()
    logger.info("Database engines disposed")
