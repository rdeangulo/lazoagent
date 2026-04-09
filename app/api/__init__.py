"""
Lazo Agent — API Routes

Agent Training Platform API structure:
- /auth          — Admin authentication (JWT)
- /agents        — Agent CRUD and configuration
- /knowledge     — Knowledge base management
- /training      — Test playground / training sessions
- /api-keys      — API key management for external services
- /b2chat        — B2Chat historical import
- /v1/chat       — Inference API (external services call this)
- /health        — Health checks
"""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.agents import router as agents_router
from app.api.knowledge import router as knowledge_router
from app.api.training import router as training_router
from app.api.api_keys import router as api_keys_router
from app.api.inference import router as inference_router
from app.api.b2chat import router as b2chat_router
from app.api.health import router as health_router

api_router = APIRouter()

# Public
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(health_router, prefix="/health", tags=["Health"])

# External services (API key auth)
api_router.include_router(inference_router, prefix="/v1", tags=["Inference API"])

# Admin (JWT auth)
api_router.include_router(agents_router, prefix="/agents", tags=["Agents"])
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["Knowledge Base"])
api_router.include_router(training_router, prefix="/training", tags=["Training"])
api_router.include_router(api_keys_router, prefix="/api-keys", tags=["API Keys"])
api_router.include_router(b2chat_router, prefix="/b2chat", tags=["B2Chat"])
