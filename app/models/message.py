"""
Lazo Agent — Message Model

Individual messages within a thread. Tracks sender type
so we can distinguish customer, AI, operator, and system messages.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

import enum


class SenderType(str, enum.Enum):
    CUSTOMER = "customer"
    ASSISTANT = "assistant"  # AI agent
    OPERATOR = "operator"    # Human agent
    SYSTEM = "system"        # Automated notifications


class ContentType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"


class Message(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "messages"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False
    )

    sender_type: Mapped[SenderType] = mapped_column(
        Enum(SenderType, name="sender_type"),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type"),
        default=ContentType.TEXT,
        nullable=False,
    )

    # External message ID (WhatsApp msg ID, Meta msg ID, etc.)
    external_id: Mapped[Optional[str]] = mapped_column(String(255))

    # For operator messages, track who sent it
    operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operators.id")
    )

    # Media URL if content_type is not text
    media_url: Mapped[Optional[str]] = mapped_column(Text)

    # Flexible metadata (tool calls, delivery status, etc.)
    meta_data: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )

    # Relationships
    thread = relationship("Thread", back_populates="messages")
    operator = relationship("Operator", foreign_keys=[operator_id])

    __table_args__ = (
        Index("ix_messages_thread_created", "thread_id", "created_at"),
        Index("ix_messages_sender", "sender_type"),
        Index("ix_messages_external", "external_id"),
    )

    def __repr__(self):
        return f"<Message {self.sender_type.value}: {self.content[:50]}>"
