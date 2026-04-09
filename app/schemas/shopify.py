"""Lazo Agent — Shopify Schemas"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrderResponse(BaseModel):
    shopify_order_id: str
    order_number: str
    status: Optional[str] = None
    financial_status: Optional[str] = None
    fulfillment_status: Optional[str] = None
    total_price: Optional[float] = None
    currency: str = "MXN"
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    carrier: Optional[str] = None
    customer_email: Optional[str] = None
    created_at: Optional[datetime] = None


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    total: int
