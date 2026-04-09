"""
Lazo Agent — Channel Model

Channels represent communication endpoints: WhatsApp, web chat,
Facebook Messenger, Instagram, email, etc.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, Column, Enum, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

import enum


class ChannelType(str, enum.Enum):
    WHATSAPP = "whatsapp"
    WEB_CHAT = "web_chat"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    EMAIL = "email"


# Association table: operators ↔ channels (many-to-many)
operator_channels = Table(
    "operator_channels",
    Base.metadata,
    Column("operator_id", UUID(as_uuid=True), ForeignKey("operators.id"), primary_key=True),
    Column("channel_id", UUID(as_uuid=True), ForeignKey("channels.id"), primary_key=True),
)


class Channel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "channels"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    channel_type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, name="channel_type"),
        nullable=False,
    )

    # Channel-specific config (phone number, page ID, API keys, etc.)
    # Stored as JSON so each channel type can have different config
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    operators = relationship(
        "Operator",
        secondary="operator_channels",
        back_populates="channels",
        lazy="selectin",
    )
    threads = relationship("Thread", back_populates="channel", lazy="selectin")

    def __repr__(self):
        return f"<Channel {self.slug} ({self.channel_type.value})>"
