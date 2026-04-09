"""
Lazo Agent — B2Chat API Service

Connects to B2Chat's Central API to pull historical conversations,
contacts, and tags. Used to build the knowledge base from real
customer interactions.

API Reference: https://api.b2chat.io
Auth: OAuth2 client_credentials → Bearer JWT (24h expiry)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from app.config import settings
from app.core.exceptions import LazoError

logger = logging.getLogger(__name__)

BASE_URL = "https://api.b2chat.io"


class B2ChatAuthError(LazoError):
    def __init__(self, message: str = "B2Chat authentication failed"):
        super().__init__(message, "B2CHAT_AUTH_ERROR")


class B2ChatAPIError(LazoError):
    def __init__(self, message: str = "B2Chat API error"):
        super().__init__(message, "B2CHAT_API_ERROR")


class B2ChatService:
    """B2Chat Central API client for pulling historical data."""

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0

    # ── Authentication ───────────────────────────────────────────────────

    async def _authenticate(self) -> str:
        """Get a Bearer token via OAuth2 client_credentials flow."""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        if not settings.B2CHAT_CLIENT_ID or not settings.B2CHAT_CLIENT_SECRET:
            raise B2ChatAuthError("B2Chat credentials not configured")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{BASE_URL}/oauth/token",
                data={"grant_type": "client_credentials"},
                auth=(settings.B2CHAT_CLIENT_ID, settings.B2CHAT_CLIENT_SECRET),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                raise B2ChatAuthError(f"Auth failed ({response.status_code}): {response.text}")

            data = response.json()
            self._access_token = data.get("access_token")
            # Refresh 1 hour before expiry (tokens last 24h)
            expires_in = data.get("expires_in", 86400)
            self._token_expiry = time.time() + expires_in - 3600

            logger.info("B2Chat authenticated (expires in %ds)", expires_in)
            return self._access_token

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make an authenticated request to the B2Chat API."""
        token = await self._authenticate()

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.request(
                method,
                f"{BASE_URL}{endpoint}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                **kwargs,
            )

            if response.status_code == 401:
                # Token expired, retry once
                self._access_token = None
                token = await self._authenticate()
                response = await client.request(
                    method,
                    f"{BASE_URL}{endpoint}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    **kwargs,
                )

            if response.status_code >= 400:
                raise B2ChatAPIError(
                    f"B2Chat API {method} {endpoint} failed ({response.status_code}): {response.text}"
                )

            return response.json()

    # ── Health ───────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Check if B2Chat API is reachable."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{BASE_URL}/health")
                return response.status_code == 200
        except Exception:
            return False

    # ── Chat Export ──────────────────────────────────────────────────────

    async def export_chats(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        messaging_provider: Optional[str] = None,
        agent_lookup: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict]:
        """Export chat conversations from B2Chat.

        Args:
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            messaging_provider: Filter by channel (whatsapp|facebook|telegram|livechat|b2cbotapi)
            agent_lookup: Filter by agent username
            limit: Max records per page (max 1000)
            offset: Pagination offset

        Returns:
            List of chat objects with messages, contact info, timestamps
        """
        params = {
            "limit": min(limit, 1000),
            "offset": offset,
            "order_dir": "desc",
        }
        if date_from:
            params["date_range_from"] = date_from
        if date_to:
            params["date_range_to"] = date_to
        if messaging_provider:
            params["messaging_provider"] = messaging_provider
        if agent_lookup:
            params["agent_lookup"] = agent_lookup

        data = await self._request("GET", "/chats/export", params=params)

        # B2Chat returns the chats directly or nested — handle both
        if isinstance(data, list):
            return data
        return data.get("chats", data.get("data", []))

    async def export_all_chats(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        messaging_provider: Optional[str] = None,
        max_chats: int = 10000,
    ) -> list[dict]:
        """Export ALL chats with automatic pagination.

        Paginates through the API until no more results or max_chats reached.
        """
        all_chats = []
        offset = 0
        batch_size = 200  # B2Chat API can timeout with larger batches + date filters

        while len(all_chats) < max_chats:
            batch = await self.export_chats(
                date_from=date_from,
                date_to=date_to,
                messaging_provider=messaging_provider,
                limit=batch_size,
                offset=offset,
            )

            if not batch:
                break

            all_chats.extend(batch)
            offset += batch_size

            logger.info(
                "B2Chat export: fetched %d chats (total: %d)",
                len(batch), len(all_chats),
            )

            # If we got fewer than requested, we've reached the end
            if len(batch) < batch_size:
                break

        return all_chats[:max_chats]

    # ── Contacts ─────────────────────────────────────────────────────────

    async def export_contacts(
        self,
        limit: int = 1000,
        offset: int = 0,
        contact_lookup: Optional[str] = None,
    ) -> list[dict]:
        """Export contacts from B2Chat."""
        params = {
            "limit": min(limit, 1000),
            "offset": offset,
            "skip_custom_attributes": "false",
            "skip_tags": "false",
        }
        if contact_lookup:
            params["contact_lookup"] = contact_lookup

        data = await self._request("GET", "/contacts/export", params=params)

        if isinstance(data, list):
            return data
        return data.get("contacts", data.get("data", []))

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def extract_messages_from_chat(chat: dict) -> list[dict]:
        """Extract individual messages from a B2Chat chat object.

        B2Chat message format:
        - incoming: true = customer, false = agent
        - body: message text
        - type: TEXT, IMAGE, AUDIO, etc.
        - created_at: timestamp

        Returns a list of dicts with:
        - role: 'customer' or 'agent'
        - content: message text
        - timestamp: message time
        """
        messages = []
        raw_messages = chat.get("messages", chat.get("conversation", []))

        if isinstance(raw_messages, list):
            for msg in raw_messages:
                # B2Chat uses 'incoming' boolean: true = customer, false = agent
                if "incoming" in msg:
                    role = "customer" if msg["incoming"] else "agent"
                elif msg.get("fromAgent"):
                    role = "agent"
                else:
                    role = "customer"

                content = msg.get("body") or msg.get("text") or msg.get("content") or ""

                # Skip media URLs and empty messages
                if not content or not content.strip():
                    continue
                if content.startswith(("https://lookaside.fbsbx.com/",
                                       "https://scontent",
                                       "https://b2chat-filesrepo.s3.",
                                       "https://b2chat.io/",
                                       "https://app.b2chat.io/")):
                    continue
                # Skip pure URLs with no other text
                stripped = content.strip()
                if stripped.startswith("https://") and " " not in stripped:
                    continue

                messages.append({
                    "role": role,
                    "content": content.strip(),
                    "timestamp": msg.get("created_at") or msg.get("timestamp") or "",
                    "type": msg.get("type", "TEXT"),
                })

        return messages

    @staticmethod
    def format_chat_as_text(chat: dict) -> str:
        """Format a chat into a readable text block for knowledge extraction."""
        messages = B2ChatService.extract_messages_from_chat(chat)
        if not messages:
            return ""

        # B2Chat uses 'provider' for channel type
        channel = chat.get("provider") or chat.get("messaging_provider") or "unknown"
        contact_name = (
            chat.get("contact", {}).get("name")
            or chat.get("contact", {}).get("fullname")
            or chat.get("contact_name")
            or "Customer"
        )
        department = chat.get("department") or ""
        agent_name = chat.get("agent", {}).get("name") or ""

        header = f"[Channel: {channel} | Customer: {contact_name}"
        if department:
            header += f" | Dept: {department}"
        if agent_name:
            header += f" | Agent: {agent_name}"
        header += "]"

        lines = [header]
        for msg in messages:
            prefix = "CUSTOMER" if msg["role"] == "customer" else "AGENT"
            lines.append(f"{prefix}: {msg['content']}")

        return "\n".join(lines)


# Singleton
b2chat_service = B2ChatService()
