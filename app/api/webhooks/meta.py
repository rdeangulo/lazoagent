"""Lazo Agent — Meta (Facebook/Instagram/WhatsApp Cloud API) Webhook"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.core.security import verify_meta_signature

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/webhook")
async def meta_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification (GET request for subscription)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def meta_webhook(request: Request):
    """Handle incoming messages from Facebook, Instagram, and WhatsApp Cloud API.

    Meta sends all messaging events to this single endpoint.
    We route based on the messaging platform in the payload.
    """
    # Verify signature
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if settings.META_APP_SECRET and not verify_meta_signature(body, signature):
        logger.warning("Invalid Meta webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    obj = payload.get("object")

    if obj == "whatsapp_business_account":
        await _handle_whatsapp_cloud(payload)
    elif obj == "page":
        await _handle_facebook(payload)
    elif obj == "instagram":
        await _handle_instagram(payload)

    return PlainTextResponse("OK")


async def _handle_whatsapp_cloud(payload: dict):
    """Process WhatsApp Cloud API messages."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            for msg in messages:
                from_number = msg.get("from", "")
                msg_type = msg.get("type", "")
                text = ""

                if msg_type == "text":
                    text = msg.get("text", {}).get("body", "")
                elif msg_type == "audio":
                    # TODO: transcribe audio
                    text = "[Audio message received]"
                else:
                    text = f"[{msg_type} message received]"

                if text:
                    logger.info("WhatsApp Cloud msg from %s: %s", from_number, text[:100])
                    # TODO: Process through thread system (same as Twilio flow)


async def _handle_facebook(payload: dict):
    """Process Facebook Messenger messages."""
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id", "")
            message = event.get("message", {})
            text = message.get("text", "")

            if text:
                logger.info("Facebook msg from %s: %s", sender_id, text[:100])
                # TODO: Process through thread system


async def _handle_instagram(payload: dict):
    """Process Instagram Direct messages."""
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id", "")
            message = event.get("message", {})
            text = message.get("text", "")

            if text:
                logger.info("Instagram msg from %s: %s", sender_id, text[:100])
                # TODO: Process through thread system
