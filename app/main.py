"""
Lazo Agent — FastAPI Application Entry Point

This is the main application file. It:
1. Creates the FastAPI app
2. Registers middleware (CORS, rate limiting)
3. Mounts all API routers
4. Sets up startup/shutdown lifecycle events
5. Serves static files for the CRM SPA
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.config import settings
from app.middleware.cors import setup_cors
from app.middleware.rate_limit import RateLimitMiddleware

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown events."""
    # ── Startup ──────────────────────────────────────────────────────
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.APP_ENV)

    # Initialize Redis
    from app.core.redis import get_redis
    await get_redis()

    # Start WebSocket manager background tasks
    from app.core.websocket_manager import ws_manager
    await ws_manager.start()

    # Initialize Sentry if configured
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.APP_ENV,
                traces_sample_rate=0.1,
            )
            logger.info("Sentry initialized")
        except Exception as e:
            logger.warning("Failed to initialize Sentry: %s", e)

    logger.info("%s is ready", settings.APP_NAME)

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down %s", settings.APP_NAME)

    await ws_manager.stop()

    from app.core.redis import close_redis
    await close_redis()

    from app.core.database import dispose_engines
    await dispose_engines()

    logger.info("Shutdown complete")


# ── Create App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered customer service platform for Lazo retail & e-commerce",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.is_development else None,
    redoc_url="/api/redoc" if settings.is_development else None,
)

# ── Middleware ────────────────────────────────────────────────────────────────

setup_cors(app)
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# ── Routes ───────────────────────────────────────────────────────────────────

app.include_router(api_router, prefix="/api")

# ── Static Files (CRM SPA) ──────────────────────────────────────────────────

import os

crm_static = os.path.join(os.path.dirname(__file__), "static", "crm")
if os.path.isdir(crm_static):
    app.mount("/crm", StaticFiles(directory=crm_static, html=True), name="crm")


# ── Root ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/api/docs" if settings.is_development else None,
    }
