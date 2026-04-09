"""
Lazo Agent — Thread Model

A Thread is a single conversation between a customer and the AI/operator.
Tracks status transitions: active → escalated → taken → closed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

import enum


class ThreadStatus(str, enum.Enum):
    ACTIVE = "active"           # AI is handling
    ESCALATED = "escalated"     # Waiting for human agent
    TAKEN = "taken"             # Human agent has taken over
    INBOX = "inbox"             # No agent available, queued for follow-up
    CLOSED = "closed"           # Resolved


class Thread(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "threads"

    # Relationships
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id")
    )
    channel_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.id")
    )
    operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operators.id")
    )

    # Status
    status: Mapped[ThreadStatus] = mapped_column(
        Enum(ThreadStatus, name="thread_status"),
        default=ThreadStatus.ACTIVE,
        nullable=False,
    )

    # Context
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    language: Mapped[str] = mapped_column(String(10), default="es")
    closed_reason: Mapped[Optional[str]] = mapped_column(String(100))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Escalation info
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Inbox info (contact captured for follow-up)
    inbox_contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    inbox_contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    inbox_note: Mapped[Optional[str]] = mapped_column(Text)

    # Flexible metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )

    # AI conversation summary (for handoff context)
    conversation_summary: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    customer = relationship("Customer", back_populates="threads")
    channel = relationship("Channel", back_populates="threads")
    operator = relationship("Operator", foreign_keys=[operator_id])
    messages = relationship("Message", back_populates="thread", lazy="selectin", order_by="Message.created_at")
    escalation = relationship("Escalation", back_populates="thread", uselist=False)

    __table_args__ = (
        Index("ix_threads_status", "status"),
        Index("ix_threads_customer", "customer_id"),
        Index("ix_threads_channel_status", "channel_id", "status"),
        Index("ix_threads_created", "created_at"),
    )

    def __repr__(self):
        return f"<Thread {self.id} ({self.status.value})>"
