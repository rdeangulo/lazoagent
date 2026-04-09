"""Lazo Agent — Webhook Routes"""

from fastapi import APIRouter

from app.api.webhooks.twilio import router as twilio_router
from app.api.webhooks.meta import router as meta_router
from app.api.webhooks.shopify_wh import router as shopify_router

router = APIRouter()
router.include_router(twilio_router, prefix="/twilio", tags=["Twilio Webhooks"])
router.include_router(meta_router, prefix="/meta", tags=["Meta Webhooks"])
router.include_router(shopify_router, prefix="/shopify", tags=["Shopify Webhooks"])
