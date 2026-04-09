"""Lazo Agent — Shopify Routes (CRM-facing)"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_operator
from app.services.shopify_service import shopify_service

router = APIRouter()


@router.get("/orders")
async def search_orders(
    email: Optional[str] = Query(None),
    order_number: Optional[str] = Query(None),
    limit: int = Query(10, le=50),
    operator: dict = Depends(get_current_operator),
):
    """Search Shopify orders by email or order number."""
    if order_number:
        order = await shopify_service.get_order_by_number(order_number)
        return {"orders": [order] if order else [], "total": 1 if order else 0}

    if email:
        orders = await shopify_service.get_orders_by_email(email, limit)
        return {"orders": orders, "total": len(orders)}

    return {"orders": [], "total": 0}


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    operator: dict = Depends(get_current_operator),
):
    """Get a specific Shopify order."""
    order = await shopify_service.get_order_by_id(order_id)
    if not order:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Order not found")
    return order
