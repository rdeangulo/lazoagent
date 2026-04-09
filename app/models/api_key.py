"""
Lazo Agent — API Key Model

API keys authenticate external services (CRMs, channel connectors, etc.)
that call the inference API. Each key is scoped to specific agents.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ApiKey(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "api_keys"

    # The key itself (hashed for storage, shown once on creation)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)  # First 8 chars for identification
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # "Lazo CRM Production"
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Scope: which agents this key can access (null = all)
    agent_ids: Mapped[Optional[list]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Expiry (null = never expires)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_api_keys_hash", "key_hash"),
        Index("ix_api_keys_prefix", "key_prefix"),
    )

    @staticmethod
    def generate_key() -> str:
        """Generate a new API key. Format: lz_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"""
        return f"lz_{secrets.token_hex(24)}"

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key for storage."""
        import hashlib
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def get_prefix(key: str) -> str:
        """Get the prefix (first 8 chars) for identification."""
        return key[:8]

    def __repr__(self):
        return f"<ApiKey {self.name} ({self.key_prefix}...)>"
