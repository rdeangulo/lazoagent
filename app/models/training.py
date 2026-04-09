"""
Lazo Agent — Training & Playground Models

TrainingSessions let admins test agents with sample conversations
before deploying. Each session records messages, tool calls,
and quality metrics.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

import enum


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


class TrainingSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "training_sessions"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )

    # Session info
    title: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"),
        default=SessionStatus.ACTIVE,
        nullable=False,
    )

    # Conversation messages (stored as JSON array)
    # Each message: {role, content, timestamp, tool_calls?, tool_results?}
    messages: Mapped[Optional[list]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
    )

    # Quality tracking
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0)
    knowledge_hits: Mapped[int] = mapped_column(Integer, default=0)

    # Feedback (admin rates the session)
    rating: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    feedback_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    meta_data: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )

    # Relationships
    agent = relationship("Agent")

    __table_args__ = (
        Index("ix_training_sessions_agent", "agent_id"),
        Index("ix_training_sessions_status", "status"),
    )

    def __repr__(self):
        return f"<TrainingSession {self.id} (agent={self.agent_id}, msgs={self.message_count})>"
