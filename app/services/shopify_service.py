"""
Lazo Agent — Shopify Service

Handles all communication with the Shopify Admin API.
Provides order lookup, customer search, and webhook processing.
Caches results in the local database for faster AI tool responses.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings
from app.core.exceptions import ShopifyAuthError, ShopifyError, ShopifyNotFoundError

logger = logging.getLogger(__name__)


class ShopifyService:
    """Shopify Admin API client."""

    def __init__(self):
        self._base_url: Optional[str] = None
        self._headers: Optional[dict] = None

    @property
    def base_url(self) -> str:
        if not self._base_url:
            if not settings.SHOPIFY_STORE_URL or not settings.SHOPIFY_ACCESS_TOKEN:
                raise ShopifyAuthError()
            self._base_url = (
                f"https://{settings.SHOPIFY_STORE_URL}/admin/api/{settings.SHOPIFY_API_VERSION}"
            )
        return self._base_url

    @property
    def headers(self) -> dict:
        if not self._headers:
            self._headers = {
                "X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN,
                "Content-Type": "application/json",
            }
        return self._headers

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an authenticated request to the Shopify Admin API."""
        url = f"{self.base_url}/{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, url, headers=self.headers, **kwargs)

            if response.status_code == 401:
                raise ShopifyAuthError()
            if response.status_code == 404:
                raise ShopifyNotFoundError(endpoint)
            if response.status_code >= 400:
                raise ShopifyError(f"Shopify API error {response.status_code}: {response.text}")

            return response.json()

    # ── Orders ───────────────────────────────────────────────────────────

    async def get_order_by_number(self, order_number: str) -> Optional[dict]:
        """Look up an order by its number (e.g., "#1234" or "1234")."""
        order_number = order_number.strip().lstrip("#")

        data = await self._request(
            "GET",
            f"orders.json?name=%23{order_number}&status=any",
        )
        orders = data.get("orders", [])
        if not orders:
            return None

        return self._format_order(orders[0])

    async def get_order_by_id(self, shopify_order_id: str) -> Optional[dict]:
        """Look up an order by its Shopify ID."""
        data = await self._request("GET", f"orders/{shopify_order_id}.json")
        order = data.get("order")
        return self._format_order(order) if order else None

    async def get_orders_by_email(self, email: str, limit: int = 5) -> list[dict]:
        """Get recent orders for a customer email."""
        data = await self._request(
            "GET",
            f"orders.json?email={email}&status=any&limit={limit}",
        )
        return [self._format_order(o) for o in data.get("orders", [])]

    # ── Customers ────────────────────────────────────────────────────────

    async def search_customer(self, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[dict]:
        """Search for a Shopify customer by email or phone."""
        query = email or phone
        if not query:
            return None

        data = await self._request("GET", f"customers/search.json?query={query}")
        customers = data.get("customers", [])
        return customers[0] if customers else None

    # ── Webhooks ─────────────────────────────────────────────────────────

    async def process_order_webhook(self, topic: str, payload: dict) -> dict:
        """Process an incoming Shopify order webhook.

        Updates the local cache and returns the formatted order.
        """
        order = self._format_order(payload)

        # Cache in database (fire-and-forget in production)
        await self._cache_order(order)

        return order

    # ── Helpers ───────────────────────────────────────────────────────────

    def _format_order(self, order: dict) -> dict:
        """Extract relevant order fields into a clean dict."""
        fulfillments = order.get("fulfillments", [])
        tracking = None
        tracking_url = None
        carrier = None

        if fulfillments:
            latest = fulfillments[-1]
            tracking = latest.get("tracking_number")
            tracking_url = latest.get("tracking_url")
            carrier = latest.get("tracking_company")

        return {
            "shopify_order_id": str(order.get("id")),
            "order_number": str(order.get("order_number", order.get("name", ""))).lstrip("#"),
            "status": order.get("status", "open"),
            "financial_status": order.get("financial_status"),
            "fulfillment_status": order.get("fulfillment_status") or "unfulfilled",
            "total_price": order.get("total_price"),
            "currency": order.get("currency", "MXN"),
            "tracking_number": tracking,
            "tracking_url": tracking_url,
            "carrier": carrier,
            "customer_email": order.get("email"),
            "shopify_customer_id": str(order.get("customer", {}).get("id", "")),
            "created_at": order.get("created_at"),
            "updated_at": order.get("updated_at"),
        }

    async def _cache_order(self, order: dict):
        """Cache/update order data in the local database."""
        from app.core.database import get_db_context
        from app.models import ShopifyOrder
        from sqlalchemy import select

        try:
            async with get_db_context() as db:
                stmt = select(ShopifyOrder).where(
                    ShopifyOrder.shopify_order_id == order["shopify_order_id"]
                )
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    for key, value in order.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                else:
                    db.add(ShopifyOrder(**order))
        except Exception as e:
            logger.warning("Failed to cache Shopify order: %s", e)


# Singleton
shopify_service = ShopifyService()
