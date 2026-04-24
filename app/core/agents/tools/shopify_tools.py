"""
Lazo Agent — Shopify Tools

Agent tools for looking up order status on demand.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool


@tool
async def check_order_status(
    order_number: Optional[str] = None,
    email: Optional[str] = None,
) -> str:
    """Check the status of a Shopify order.

    Use this when the customer asks about the status of an order they placed —
    whether it has shipped, tracking info, fulfillment state, or payment status.
    Pass the order number (e.g. "#1001") if the customer provided one, and/or
    their email. At least one is required.

    Args:
        order_number: Shopify order name/number (e.g. "#1001" or "1001")
        email: Customer email associated with the order
    """
    from app.services.shopify_service import shopify_service

    if not shopify_service.is_configured:
        return "Shopify is not configured for this store, so I cannot check order status right now."

    if not order_number and not email:
        return "I need either an order number or the email used to place the order to look it up."

    order = await shopify_service.find_order(order_name=order_number, email=email)
    if not order:
        hint = order_number or email
        return f"I could not find any order matching '{hint}'. Please double-check the details."

    summary = shopify_service.summarize_order(order)

    lines = [
        f"Order {summary['name']}",
        f"Placed: {summary['created_at']}",
        f"Payment: {summary['financial_status']}",
        f"Fulfillment: {summary['fulfillment_status']}",
        f"Total: {summary['total_price']} {summary['currency']}",
    ]

    if summary["line_items"]:
        items = ", ".join(f"{li['quantity']}x {li['title']}" for li in summary["line_items"])
        lines.append(f"Items: {items}")

    if summary["tracking"]:
        parts = []
        for t in summary["tracking"]:
            label = t.get("company") or "Tracking"
            num = t.get("number") or ""
            url = t.get("url") or ""
            parts.append(f"{label} {num} {url}".strip())
        lines.append("Tracking: " + "; ".join(parts))

    return "\n".join(lines)
