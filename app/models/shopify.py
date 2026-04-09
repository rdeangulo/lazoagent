"""
Lazo Agent — Shopify Models

Caches Shopify order data for quick lookup during conversations.
The AI uses this to check order status without hitting the Shopify API every time.
Webhook logs track all incoming Shopify events.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ShopifyOrder(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "shopify_orders"

    # Shopify identifiers
    shopify_order_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    order_number: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    # Customer link
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    shopify_customer_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    # Order details
    status: Mapped[Optional[str]] = mapped_column(String(50))  # open, closed, cancelled
    financial_status: Mapped[Optional[str]] = mapped_column(String(50))  # paid, pending, refunded
    fulfillment_status: Mapped[Optional[str]] = mapped_column(String(50))  # fulfilled, partial, null

    total_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(10), default="MXN")

    # Tracking
    tracking_number: Mapped[Optional[str]] = mapped_column(String(255))
    tracking_url: Mapped[Optional[str]] = mapped_column(Text)
    carrier: Mapped[Optional[str]] = mapped_column(String(100))

    # Timestamps from Shopify
    shopify_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    shopify_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Full order data snapshot
    order_data: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )

    __table_args__ = (
        Index("ix_shopify_orders_status", "status"),
        Index("ix_shopify_orders_email", "customer_email"),
    )

    def __repr__(self):
        return f"<ShopifyOrder #{self.order_number} ({self.status})>"


class ShopifyWebhookLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "shopify_webhook_logs"

    topic: Mapped[str] = mapped_column(String(100), nullable=False)  # orders/create, orders/updated, etc.
    shopify_order_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    processed: Mapped[bool] = mapped_column(default=False)
    error: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("ix_webhook_logs_topic", "topic"),
    )
