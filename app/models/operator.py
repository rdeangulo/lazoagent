"""
Lazo Agent — Operator Model

Operators are human agents who handle escalated conversations
and manage the CRM/inbox when online.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

import enum


class OperatorRole(str, enum.Enum):
    ADMIN = "admin"
    AGENT = "agent"


class OperatorStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"


class Operator(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "operators"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    role: Mapped[OperatorRole] = mapped_column(
        Enum(OperatorRole, name="operator_role"),
        default=OperatorRole.AGENT,
        nullable=False,
    )
    status: Mapped[OperatorStatus] = mapped_column(
        Enum(OperatorStatus, name="operator_status"),
        default=OperatorStatus.OFFLINE,
        nullable=False,
    )

    # Email verification
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_token: Mapped[Optional[str]] = mapped_column(String(255))

    # Password reset
    reset_token: Mapped[Optional[str]] = mapped_column(String(255))
    reset_token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Session tracking
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    channels = relationship(
        "Channel",
        secondary="operator_channels",
        back_populates="operators",
        lazy="selectin",
    )
    escalations = relationship("Escalation", back_populates="assigned_operator", lazy="selectin")
    logs = relationship("OperatorLog", back_populates="operator", lazy="selectin")

    def __repr__(self):
        return f"<Operator {self.name} ({self.status.value})>"


class OperatorLog(Base, UUIDMixin):
    __tablename__ = "operator_logs"

    operator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("operators.id"), nullable=False
    )
    event: Mapped[str] = mapped_column(String(50), nullable=False)  # login, logout, status_change
    detail: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    operator = relationship("Operator", back_populates="logs")

    __table_args__ = (
        Index("ix_operator_logs_operator_timestamp", "operator_id", "timestamp"),
    )
