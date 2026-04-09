"""
Lazo Agent — Agent Model

An Agent is an independently configurable AI assistant with its own
persona, instructions, tools, LLM settings, and linked knowledge base.
This is the core entity of the training platform.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Enum, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

import enum


class AgentStatus(str, enum.Enum):
    DRAFT = "draft"         # Being configured, not deployed
    ACTIVE = "active"       # Live, accepting messages
    PAUSED = "paused"       # Temporarily disabled
    ARCHIVED = "archived"   # No longer in use


class Agent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agents"

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, name="agent_status"),
        default=AgentStatus.DRAFT,
        nullable=False,
    )

    # ── Persona & Instructions ───────────────────────────────────────────
    # The system prompt that defines the agent's personality and behavior
    system_prompt: Mapped[Optional[str]] = mapped_column(Text)

    # Language defaults
    default_language: Mapped[str] = mapped_column(String(10), default="es")

    # ── LLM Configuration ────────────────────────────────────────────────
    # Provider: "anthropic" or "openai"
    llm_provider: Mapped[str] = mapped_column(String(50), default="openai")
    llm_model: Mapped[str] = mapped_column(String(100), default="gpt-4.1-mini")
    temperature: Mapped[float] = mapped_column(default=0.3)
    max_tokens: Mapped[int] = mapped_column(default=4096)

    # ── Tools Configuration ──────────────────────────────────────────────
    # Which tools are enabled for this agent (list of tool names)
    enabled_tools: Mapped[Optional[list]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
    )

    # ── Knowledge Base Link ──────────────────────────────────────────────
    # Which document types this agent can search (null = all)
    knowledge_doc_types: Mapped[Optional[list]] = mapped_column(
        MutableList.as_mutable(JSONB),
        default=list,
    )

    # RAG settings
    knowledge_search_limit: Mapped[int] = mapped_column(default=5)
    knowledge_score_threshold: Mapped[float] = mapped_column(default=0.3)

    # ── Behavior Settings ────────────────────────────────────────────────
    # Flexible config for agent-specific behavior
    config: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )

    # ── Langfuse ─────────────────────────────────────────────────────────
    # Optional Langfuse prompt name (overrides system_prompt if set)
    langfuse_prompt_name: Mapped[Optional[str]] = mapped_column(String(255))

    __table_args__ = (
        Index("ix_agents_status", "status"),
        Index("ix_agents_slug", "slug"),
    )

    def __repr__(self):
        return f"<Agent {self.name} ({self.status.value})>"
