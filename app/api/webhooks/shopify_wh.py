"""Lazo Agent — Shopify Webhook Handler"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/orders")
async def shopify_order_webhook(request: Request):
    """Handle Shopify order webhooks (orders/create, orders/updated, etc.)

    Updates the local order cache so AI tools have fresh data.
    """
    # Verify HMAC signature
    body = await request.body()
    signature = request.headers.get("X-Shopify-Hmac-Sha256", "")
    topic = request.headers.get("X-Shopify-Topic", "unknown")

    if settings.SHOPIFY_WEBHOOK_SECRET:
        computed = hmac.new(
            settings.SHOPIFY_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).digest()

        import base64
        expected = base64.b64encode(computed).decode()

        if not hmac.compare_digest(expected, signature):
            logger.warning("Invalid Shopify webhook signature for topic: %s", topic)
            raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    logger.info("Shopify webhook: %s (order %s)", topic, payload.get("order_number"))

    # Process the webhook
    from app.services.shopify_service import shopify_service
    from app.core.database import get_db_context
    from app.models import ShopifyWebhookLog

    # Log the webhook
    async with get_db_context() as db:
        log = ShopifyWebhookLog(
            topic=topic,
            shopify_order_id=str(payload.get("id", "")),
            payload=payload,
        )
        db.add(log)

    # Update cached order data
    try:
        await shopify_service.process_order_webhook(topic, payload)
    except Exception as e:
        logger.error("Failed to process Shopify webhook: %s", e)

    return PlainTextResponse("OK")
