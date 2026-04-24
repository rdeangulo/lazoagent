"""
Lazo Agent — Shopify Service

Async client for the Shopify GraphQL Admin API. Used by agent tools
to look up order status on demand. GraphQL is the supported path —
REST was marked legacy on 2024-10-01.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


ORDER_FIELDS = """
name
createdAt
displayFinancialStatus
displayFulfillmentStatus
totalPriceSet { shopMoney { amount currencyCode } }
customer { email }
lineItems(first: 20) {
  edges { node { title quantity } }
}
fulfillments(first: 10) {
  trackingInfo { number url company }
}
"""

FIND_ORDER_QUERY = f"""
query findOrder($query: String!) {{
  orders(first: 1, sortKey: CREATED_AT, reverse: true, query: $query) {{
    edges {{ node {{ {ORDER_FIELDS} }} }}
  }}
}}
"""


class ShopifyService:
    def __init__(self) -> None:
        self.store_url = settings.SHOPIFY_STORE_URL
        self.access_token = settings.SHOPIFY_ACCESS_TOKEN
        self.api_version = settings.SHOPIFY_API_VERSION

    @property
    def is_configured(self) -> bool:
        return bool(self.store_url and self.access_token)

    def _graphql_url(self) -> str:
        return f"https://{self.store_url}/admin/api/{self.api_version}/graphql.json"

    def _headers(self) -> dict[str, str]:
        return {
            "X-Shopify-Access-Token": self.access_token or "",
            "Content-Type": "application/json",
        }

    async def _graphql(
        self,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        *,
        max_retries: int = 3,
    ) -> Optional[dict[str, Any]]:
        """Execute a GraphQL query with cost-aware THROTTLED retry."""
        payload = {"query": query, "variables": variables or {}}

        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(max_retries):
                try:
                    resp = await client.post(
                        self._graphql_url(),
                        headers=self._headers(),
                        json=payload,
                    )
                    resp.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    logger.error("Shopify GraphQL HTTP error: %s", exc.response.text)
                    return None
                except httpx.HTTPError as exc:
                    logger.error("Shopify GraphQL transport error: %s", exc)
                    return None

                body = resp.json()
                errors = body.get("errors") or []
                throttled = any(
                    (e.get("extensions") or {}).get("code") == "THROTTLED"
                    for e in errors
                )
                if throttled and attempt < max_retries - 1:
                    cost = (body.get("extensions") or {}).get("cost") or {}
                    throttle_status = cost.get("throttleStatus") or {}
                    needed = cost.get("requestedQueryCost", 50)
                    available = throttle_status.get("currentlyAvailable", 0)
                    restore_rate = throttle_status.get("restoreRate", 50)
                    wait = max((needed - available) / max(restore_rate, 1), 1.0)
                    logger.warning("Shopify THROTTLED — backing off %.1fs", wait)
                    await asyncio.sleep(wait)
                    continue

                if errors:
                    logger.error("Shopify GraphQL errors: %s", errors)
                    return None

                return body.get("data")

            logger.error("Shopify GraphQL retries exhausted")
            return None

    async def find_order(
        self,
        order_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Find an order by name (e.g. '#1001') or customer email.

        Returns the most recent matching order as a flattened dict, or None.
        """
        if not self.is_configured:
            logger.warning("Shopify not configured; cannot look up order")
            return None
        if not order_name and not email:
            return None

        clauses = []
        if order_name:
            clauses.append(f'name:"{order_name.lstrip("#")}"')
        if email:
            clauses.append(f'email:"{email}"')

        data = await self._graphql(FIND_ORDER_QUERY, {"query": " ".join(clauses)})
        if not data:
            return None

        edges = (data.get("orders") or {}).get("edges") or []
        return edges[0]["node"] if edges else None

    @staticmethod
    def summarize_order(order: dict[str, Any]) -> dict[str, Any]:
        """Reduce a GraphQL order node to the fields we surface to the LLM."""
        tracking = []
        for f in order.get("fulfillments") or []:
            for info in f.get("trackingInfo") or []:
                tracking.append(
                    {
                        "number": info.get("number"),
                        "url": info.get("url"),
                        "company": info.get("company"),
                    }
                )

        total = ((order.get("totalPriceSet") or {}).get("shopMoney")) or {}
        line_items = [
            {"title": e["node"].get("title"), "quantity": e["node"].get("quantity")}
            for e in ((order.get("lineItems") or {}).get("edges") or [])
        ]

        return {
            "name": order.get("name"),
            "financial_status": (order.get("displayFinancialStatus") or "").lower(),
            "fulfillment_status": (
                order.get("displayFulfillmentStatus") or "unfulfilled"
            ).lower(),
            "created_at": order.get("createdAt"),
            "total_price": total.get("amount"),
            "currency": total.get("currencyCode"),
            "customer_email": (order.get("customer") or {}).get("email"),
            "tracking": tracking,
            "line_items": line_items,
        }


shopify_service = ShopifyService()
