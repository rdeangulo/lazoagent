"""
Lazo Agent — Inbox Model

When no agents are available, conversations are captured in the inbox
with customer contact data for follow-up. This is the core of the
"we'll get back to you" system.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

import enum


class InboxStatus(str, enum.Enum):
    NEW = "new"                 # Just arrived, unread
    IN_PROGRESS = "in_progress"  # Agent is working on it
    RESOLVED = "resolved"       # Follow-up completed
    EXPIRED = "expired"         # SLA breached, never addressed


class InboxItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "inbox_items"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False
    )
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id")
    )
    assigned_operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operators.id")
    )
    channel_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.id")
    )

    status: Mapped[InboxStatus] = mapped_column(
        Enum(InboxStatus, name="inbox_status"),
        default=InboxStatus.NEW,
        nullable=False,
    )

    # Captured contact data (the whole point of the inbox)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50))
    contact_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Context
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    conversation_summary: Mapped[Optional[str]] = mapped_column(Text)
    customer_message: Mapped[Optional[str]] = mapped_column(Text)

    # SLA tracking
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Follow-up tracking
    follow_up_count: Mapped[int] = mapped_column(default=0)
    last_follow_up_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )

    # Relationships
    thread = relationship("Thread")
    customer = relationship("Customer")
    assigned_operator = relationship("Operator")
    channel = relationship("Channel")

    __table_args__ = (
        Index("ix_inbox_status", "status"),
        Index("ix_inbox_sla", "sla_deadline"),
        Index("ix_inbox_operator", "assigned_operator_id"),
        Index("ix_inbox_created", "created_at"),
    )

    def __repr__(self):
        contact = self.contact_email or self.contact_phone or "unknown"
        return f"<InboxItem {self.id} ({self.status.value}) contact={contact}>"
