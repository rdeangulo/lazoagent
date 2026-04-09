"""
Lazo Agent — AI Agent Training Platform

FastAPI application entry point.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.config import settings
from app.middleware.cors import setup_cors
from app.middleware.rate_limit import RateLimitMiddleware

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.APP_ENV)

    from app.core.redis import get_redis
    await get_redis()

    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.APP_ENV, traces_sample_rate=0.1)
        except Exception as e:
            logger.warning("Sentry init failed: %s", e)

    logger.info("%s is ready", settings.APP_NAME)
    yield

    logger.info("Shutting down %s", settings.APP_NAME)
    from app.core.redis import close_redis
    await close_redis()
    from app.core.database import dispose_engines
    await dispose_engines()


app = FastAPI(
    title=settings.APP_NAME,
    description="AI Agent Training Platform — create, train, and deploy AI agents with knowledge base and external API integration",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.is_development else None,
    redoc_url="/api/redoc" if settings.is_development else None,
)

setup_cors(app)
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "2.0.0",
        "type": "AI Agent Training Platform",
        "docs": "/api/docs" if settings.is_development else None,
    }
