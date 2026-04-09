"""
Lazo Agent — Escalation Model

Tracks human handoff requests. When the AI can't resolve an issue,
it creates an escalation. If an agent is online, they get it live.
If not, it feeds into the inbox system.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

import enum


class EscalationPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class EscalationStatus(str, enum.Enum):
    PENDING = "pending"       # Just created, waiting for assignment
    ASSIGNED = "assigned"     # Assigned to an operator
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    INBOX = "inbox"           # No agent available, moved to inbox


class Escalation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "escalations"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False, unique=True
    )
    assigned_operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operators.id")
    )

    priority: Mapped[EscalationPriority] = mapped_column(
        Enum(EscalationPriority, name="escalation_priority"),
        default=EscalationPriority.NORMAL,
        nullable=False,
    )
    status: Mapped[EscalationStatus] = mapped_column(
        Enum(EscalationStatus, name="escalation_status"),
        default=EscalationStatus.PENDING,
        nullable=False,
    )

    reason: Mapped[Optional[str]] = mapped_column(Text)
    conversation_summary: Mapped[Optional[str]] = mapped_column(Text)

    # Resolution
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    thread = relationship("Thread", back_populates="escalation")
    assigned_operator = relationship("Operator", back_populates="escalations")
    notes = relationship("EscalationNote", back_populates="escalation", lazy="selectin")

    __table_args__ = (
        Index("ix_escalations_status", "status"),
        Index("ix_escalations_priority_status", "priority", "status"),
        Index("ix_escalations_operator", "assigned_operator_id"),
    )

    def __repr__(self):
        return f"<Escalation {self.id} ({self.status.value}, {self.priority.value})>"


class EscalationNote(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "escalation_notes"

    escalation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("escalations.id"), nullable=False
    )
    operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operators.id")
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    escalation = relationship("Escalation", back_populates="notes")
    operator = relationship("Operator")
