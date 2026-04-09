"""
Lazo Agent — API Routes

All FastAPI routers are registered here and mounted in main.py.
"""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.threads import router as threads_router
from app.api.escalation import router as escalation_router
from app.api.inbox import router as inbox_router
from app.api.knowledge import router as knowledge_router
from app.api.channels import router as channels_router
from app.api.shopify import router as shopify_router
from app.api.analytics import router as analytics_router
from app.api.operators import router as operators_router
from app.api.health import router as health_router
from app.api.websockets import router as ws_router
from app.api.webhooks import router as webhooks_router

api_router = APIRouter()

# Public routes
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(health_router, prefix="/health", tags=["Health"])
api_router.include_router(ws_router, tags=["WebSockets"])

# Webhook routes (external services call these)
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])

# Protected routes (require operator JWT)
api_router.include_router(threads_router, prefix="/threads", tags=["Threads"])
api_router.include_router(escalation_router, prefix="/escalations", tags=["Escalations"])
api_router.include_router(inbox_router, prefix="/inbox", tags=["Inbox"])
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["Knowledge Base"])
api_router.include_router(channels_router, prefix="/channels", tags=["Channels"])
api_router.include_router(shopify_router, prefix="/shopify", tags=["Shopify"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(operators_router, prefix="/operators", tags=["Operators"])
