"""
Lazo Agent — Channel Service

Manages outbound message delivery across all channels.
Each channel type has its own delivery method (Twilio, Meta API, SMTP, etc.)
"""

from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.core.exceptions import DeliveryError
from app.models.channel import ChannelType

logger = logging.getLogger(__name__)


class ChannelService:
    """Routes outbound messages to the correct channel delivery method."""

    async def send_message(
        self,
        channel_type: str,
        recipient: str,
        message: str,
        media_url: Optional[str] = None,
    ) -> dict:
        """Send a message through the appropriate channel.

        Args:
            channel_type: The channel type (whatsapp, web_chat, facebook, instagram, email)
            recipient: Recipient identifier (phone number, user ID, email, etc.)
            message: Message text
            media_url: Optional media attachment URL

        Returns:
            dict with delivery status and external message ID
        """
        sender = self._get_sender(channel_type)
        return await sender(recipient, message, media_url)

    def _get_sender(self, channel_type: str):
        senders = {
            ChannelType.WHATSAPP.value: self._send_whatsapp,
            ChannelType.WEB_CHAT.value: self._send_web_chat,
            ChannelType.FACEBOOK.value: self._send_facebook,
            ChannelType.INSTAGRAM.value: self._send_instagram,
            ChannelType.EMAIL.value: self._send_email,
        }
        sender = senders.get(channel_type)
        if not sender:
            raise DeliveryError(channel_type, f"Unsupported channel type: {channel_type}")
        return sender

    async def _send_whatsapp(
        self, recipient: str, message: str, media_url: Optional[str] = None
    ) -> dict:
        """Send via Twilio WhatsApp API."""
        if not settings.TWILIO_ACCOUNT_SID:
            raise DeliveryError("whatsapp", "Twilio not configured")

        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        kwargs = {
            "body": message,
            "from_": f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
            "to": f"whatsapp:{recipient}",
        }
        if media_url:
            kwargs["media_url"] = [media_url]

        msg = client.messages.create(**kwargs)

        return {"external_id": msg.sid, "status": msg.status}

    async def _send_web_chat(
        self, recipient: str, message: str, media_url: Optional[str] = None
    ) -> dict:
        """Web chat messages are delivered via WebSocket — no outbound API needed."""
        from app.core.websocket_manager import ws_manager

        await ws_manager.broadcast_to_thread(recipient, {
            "type": "message",
            "sender_type": "assistant",
            "content": message,
            "media_url": media_url,
        })

        return {"external_id": None, "status": "sent"}

    async def _send_facebook(
        self, recipient: str, message: str, media_url: Optional[str] = None
    ) -> dict:
        """Send via Meta Messenger API."""
        if not settings.META_PAGE_ACCESS_TOKEN:
            raise DeliveryError("facebook", "Meta not configured")

        import httpx

        async with httpx.AsyncClient() as client:
            payload = {
                "recipient": {"id": recipient},
                "message": {"text": message},
            }
            response = await client.post(
                "https://graph.facebook.com/v18.0/me/messages",
                params={"access_token": settings.META_PAGE_ACCESS_TOKEN},
                json=payload,
            )

            if response.status_code != 200:
                raise DeliveryError("facebook", response.text)

            data = response.json()
            return {"external_id": data.get("message_id"), "status": "sent"}

    async def _send_instagram(
        self, recipient: str, message: str, media_url: Optional[str] = None
    ) -> dict:
        """Send via Meta Instagram Messaging API (same endpoint as Facebook)."""
        return await self._send_facebook(recipient, message, media_url)

    async def _send_email(
        self, recipient: str, message: str, media_url: Optional[str] = None
    ) -> dict:
        """Send via SMTP."""
        if not settings.SMTP_HOST:
            raise DeliveryError("email", "SMTP not configured")

        import aiosmtplib
        from email.mime.text import MIMEText

        msg = MIMEText(message)
        msg["Subject"] = "Lazo — Customer Support Follow-up"
        msg["From"] = settings.SMTP_USER
        msg["To"] = recipient

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=True,
        )

        return {"external_id": None, "status": "sent"}


# Singleton
channel_service = ChannelService()
