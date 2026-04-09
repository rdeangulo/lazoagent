"""
Lazo Agent — Customer Model

Represents end-customers interacting with Lazo across any channel.
Contact data is captured for inbox follow-up when no agents are available.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Customer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "customers"

    # Contact info (captured for follow-up)
    phone: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))

    # Channel identity (e.g., WhatsApp phone, FB user ID, web session)
    channel_user_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    # Profile
    language: Mapped[str] = mapped_column(String(10), default="es")
    country: Mapped[Optional[str]] = mapped_column(String(100))

    # Shopify link
    shopify_customer_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Flexible metadata (preferences, notes, etc.)
    meta_data: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )

    # Relationships
    threads = relationship("Thread", back_populates="customer", lazy="selectin")

    __table_args__ = (
        Index("ix_customers_phone_email", "phone", "email"),
    )

    def __repr__(self):
        return f"<Customer {self.name or self.phone or self.email or self.id}>"
