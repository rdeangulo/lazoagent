"""Lazo Agent — Twilio WhatsApp Webhook"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.core.security import verify_twilio_signature

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/whatsapp")
async def twilio_whatsapp_webhook(request: Request):
    """Handle incoming WhatsApp messages via Twilio.

    Flow:
    1. Verify Twilio signature
    2. Extract message and sender info
    3. Find or create thread
    4. Process through AI agent
    5. Send response back via Twilio
    """
    # Parse form data
    form = await request.form()
    params = dict(form)

    # Verify signature
    signature = request.headers.get("X-Twilio-Signature", "")
    request_url = str(request.url)

    if not verify_twilio_signature(request_url, params, signature):
        logger.warning("Invalid Twilio signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Extract message info
    from_number = params.get("From", "").replace("whatsapp:", "")
    body = params.get("Body", "")
    message_sid = params.get("MessageSid", "")

    if not body:
        return PlainTextResponse("OK")

    logger.info("WhatsApp message from %s: %s", from_number, body[:100])

    # Process the message
    from app.core.agents.bridge import process_message
    from app.core.database import get_db_context
    from app.models import Customer, Message, Thread
    from app.models.channel import ChannelType
    from app.models.message import SenderType
    from app.models.thread import ThreadStatus
    from sqlalchemy import select

    async with get_db_context() as db:
        # Find or create customer
        stmt = select(Customer).where(Customer.phone == from_number)
        result = await db.execute(stmt)
        customer = result.scalar_one_or_none()

        if not customer:
            customer = Customer(phone=from_number, channel_user_id=from_number)
            db.add(customer)
            await db.flush()

        # Find active thread or create new one
        stmt = select(Thread).where(
            Thread.customer_id == customer.id,
            Thread.status.in_([ThreadStatus.ACTIVE, ThreadStatus.ESCALATED, ThreadStatus.TAKEN]),
        ).order_by(Thread.created_at.desc())
        result = await db.execute(stmt)
        thread = result.scalar_one_or_none()

        if not thread:
            thread = Thread(
                customer_id=customer.id,
                status=ThreadStatus.ACTIVE,
                language="es",
            )
            db.add(thread)
            await db.flush()

        # Save incoming message
        msg = Message(
            thread_id=thread.id,
            sender_type=SenderType.CUSTOMER,
            content=body,
            external_id=message_sid,
        )
        db.add(msg)

    # Process through AI (only if thread is AI-handled)
    if thread.status == ThreadStatus.ACTIVE:
        ai_result = await process_message(
            message=body,
            thread_id=str(thread.id),
            channel="whatsapp",
            language=thread.language,
            customer_id=str(customer.id),
            customer_name=customer.name,
            customer_email=customer.email,
            customer_phone=customer.phone,
        )

        # Send AI response back via Twilio
        if ai_result.get("response"):
            from app.services.channel_service import channel_service
            await channel_service.send_message(
                channel_type="whatsapp",
                recipient=from_number,
                message=ai_result["response"],
            )

            # Save AI response
            async with get_db_context() as db:
                ai_msg = Message(
                    thread_id=thread.id,
                    sender_type=SenderType.ASSISTANT,
                    content=ai_result["response"],
                )
                db.add(ai_msg)

    return PlainTextResponse("OK")
