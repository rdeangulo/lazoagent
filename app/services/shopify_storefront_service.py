"""
Lazo Agent — Shopify Storefront MCP client

Wraps the public MCP endpoint at https://{shop}/api/mcp for product
discovery (catalog search, product details, policy lookup). Unlike the
Admin GraphQL client in shopify_service.py, this endpoint is public
and requires no token — it's the same data shoppers see on the store.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class ShopifyStorefrontService:
    def __init__(self) -> None:
        self.store_url = settings.SHOPIFY_STORE_URL

    @property
    def is_configured(self) -> bool:
        return bool(self.store_url)

    def _endpoint(self) -> str:
        return f"https://{self.store_url}/api/mcp"

    async def _call(self, name: str, arguments: dict) -> Optional[Any]:
        if not self.is_configured:
            logger.warning("Storefront MCP: SHOPIFY_STORE_URL not set")
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    self._endpoint(),
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                body = resp.json()
        except httpx.HTTPError as exc:
            logger.error("Storefront MCP error: %s", exc)
            return None

        if "error" in body:
            logger.error("Storefront MCP returned error: %s", body["error"])
            return None

        result = body.get("result") or {}
        content = result.get("content") or []
        if not content or content[0].get("type") != "text":
            return None
        try:
            return json.loads(content[0]["text"])
        except json.JSONDecodeError:
            logger.error("Storefront MCP returned non-JSON text")
            return None

    async def search_catalog(
        self,
        query: str,
        *,
        language: str = "es",
        currency: str = "COP",
        country: str = "CO",
    ) -> list[dict[str, Any]]:
        """Search products. Returns a compact list of products."""
        data = await self._call(
            "search_catalog",
            {
                "catalog": {
                    "query": query,
                    "context": {
                        "language": language,
                        "currency": currency,
                        "address_country": country,
                    },
                }
            },
        )
        if not data:
            return []
        return [self._summarize_search_result(p) for p in (data.get("products") or [])]

    async def get_product_details(
        self,
        product_id: str,
        *,
        options: Optional[dict[str, str]] = None,
    ) -> Optional[dict[str, Any]]:
        """Fetch a single product by Shopify gid.

        `options` can be passed to select a specific variant, e.g.
        `{"Talla": "M (30-32)"}`.
        """
        args: dict[str, Any] = {"product_id": product_id}
        if options:
            args["options"] = options

        data = await self._call("get_product_details", args)
        if not data:
            return None
        return self._summarize_detail(data.get("product") or {})

    async def search_policies(self, query: str) -> list[dict[str, str]]:
        """Search shop policies & FAQs (shipping, returns, etc.).

        Returns a list of `{question, answer}`. The Storefront MCP's
        policy indexer currently responds best to English keywords
        (e.g. "shipping", "return") — callers may want to try both
        languages.
        """
        data = await self._call(
            "search_shop_policies_and_faqs", {"query": query}
        )
        if not isinstance(data, list):
            return []
        return [
            {
                "question": item.get("question", ""),
                "answer": item.get("answer", ""),
            }
            for item in data
        ]

    @staticmethod
    def _summarize_search_result(p: dict[str, Any]) -> dict[str, Any]:
        """Normalize a product from `search_catalog` (amounts in cents)."""

        def _money(m: Optional[dict]) -> Optional[str]:
            if not m:
                return None
            amt = m.get("amount")
            cur = m.get("currency")
            if amt is None or cur is None:
                return None
            return f"{int(amt) / 100:,.0f} {cur}"

        price_range = p.get("price_range") or {}
        variants = []
        for v in p.get("variants") or []:
            variants.append(
                {
                    "title": v.get("title"),
                    "price": _money(v.get("price")),
                    "available": (v.get("availability") or {}).get("available"),
                }
            )

        return {
            "id": p.get("id"),
            "title": p.get("title"),
            "url": p.get("url"),
            "price_min": _money(price_range.get("min")),
            "price_max": _money(price_range.get("max")),
            "variants": variants,
        }

    @staticmethod
    def _summarize_detail(p: dict[str, Any]) -> dict[str, Any]:
        """Normalize a product from `get_product_details` (amounts in whole units)."""

        def _money_whole(amt: Any, cur: Optional[str]) -> Optional[str]:
            if amt is None or cur is None:
                return None
            try:
                return f"{float(amt):,.0f} {cur}"
            except (TypeError, ValueError):
                return None

        price_range = p.get("price_range") or {}
        cur = price_range.get("currency")
        selected = p.get("selectedOrFirstAvailableVariant") or {}

        options = [
            {"name": o.get("name"), "values": o.get("values") or []}
            for o in (p.get("options") or [])
        ]

        return {
            "id": p.get("product_id"),
            "title": p.get("title"),
            "description": p.get("description"),
            "url": p.get("url"),
            "image_url": p.get("image_url"),
            "options": options,
            "total_variants": p.get("total_variants"),
            "price_min": _money_whole(price_range.get("min"), cur),
            "price_max": _money_whole(price_range.get("max"), cur),
            "selected_variant": {
                "title": selected.get("title"),
                "price": _money_whole(selected.get("price"), selected.get("currency")),
                "available": selected.get("available"),
            } if selected else None,
        }


shopify_storefront_service = ShopifyStorefrontService()
