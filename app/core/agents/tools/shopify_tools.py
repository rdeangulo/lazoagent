"""
Lazo Agent — Shopify Tools

Tools for checking order status, tracking, and customer order history
via the Shopify integration.
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

    Use this when a customer asks about their order, delivery, or shipment.
    You need either the order number OR the customer's email.

    Args:
        order_number: The Shopify order number (e.g., "#1234" or "1234")
        email: Customer email to look up their orders
    """
    from app.services.shopify_service import shopify_service

    if not order_number and not email:
        return "I need either an order number or your email address to look up the order."

    try:
        if order_number:
            order = await shopify_service.get_order_by_number(order_number)
        else:
            orders = await shopify_service.get_orders_by_email(email, limit=1)
            order = orders[0] if orders else None

        if not order:
            return f"I couldn't find an order with {'number ' + order_number if order_number else 'email ' + email}. Please double-check the information."

        # Format order info
        lines = [
            f"Order #{order.get('order_number', 'N/A')}",
            f"Status: {order.get('status', 'N/A')}",
            f"Financial: {order.get('financial_status', 'N/A')}",
            f"Fulfillment: {order.get('fulfillment_status', 'unfulfilled')}",
            f"Total: {order.get('total_price', 'N/A')} {order.get('currency', 'MXN')}",
        ]

        tracking = order.get("tracking_number")
        if tracking:
            lines.append(f"Tracking: {tracking}")
            tracking_url = order.get("tracking_url")
            if tracking_url:
                lines.append(f"Track here: {tracking_url}")

        return "\n".join(lines)

    except Exception as e:
        return f"I had trouble looking up the order. Please try again or I can connect you with a team member. Error: {str(e)}"


@tool
async def get_order_history(email: str, limit: int = 5) -> str:
    """Get a customer's recent order history from Shopify.

    Use this when a customer wants to see their past orders.

    Args:
        email: Customer email address
        limit: Maximum number of orders to return
    """
    from app.services.shopify_service import shopify_service

    try:
        orders = await shopify_service.get_orders_by_email(email, limit=limit)

        if not orders:
            return f"No orders found for {email}."

        lines = [f"Found {len(orders)} recent order(s):\n"]
        for order in orders:
            lines.append(
                f"- Order #{order.get('order_number')} | "
                f"{order.get('status', 'N/A')} | "
                f"{order.get('total_price', 'N/A')} {order.get('currency', 'MXN')} | "
                f"{order.get('created_at', 'N/A')}"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"I had trouble retrieving order history. Error: {str(e)}"
