"""
Lazo Agent — Knowledge Base Models

Documents uploaded for AI training are chunked and embedded into pgvector
for RAG (Retrieval-Augmented Generation). Langfuse manages the prompts;
this manages the knowledge base content.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

# pgvector column type — imported at runtime to avoid hard dependency
# during migrations without the extension enabled
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

import enum


class DocumentType(str, enum.Enum):
    FAQ = "faq"
    POLICY = "policy"
    PRODUCT = "product"
    GUIDE = "guide"
    GENERAL = "general"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"       # Uploaded, not yet processed
    PROCESSING = "processing"  # Chunking + embedding in progress
    READY = "ready"           # Available for RAG queries
    ERROR = "error"           # Processing failed


class KnowledgeDocument(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[Optional[str]] = mapped_column(Text)

    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"),
        default=DocumentType.GENERAL,
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"),
        default=DocumentStatus.PENDING,
        nullable=False,
    )

    # Original content (full text)
    content: Mapped[Optional[str]] = mapped_column(Text)

    # Processing stats
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata (tags, category, etc.)
    meta_data: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )

    # Uploaded by
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True
    )

    # Relationships
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")
    uploaded_by = relationship("Admin")

    __table_args__ = (
        Index("ix_knowledge_docs_status", "status"),
        Index("ix_knowledge_docs_type", "doc_type"),
    )

    def __repr__(self):
        return f"<KnowledgeDocument {self.title} ({self.status.value})>"


class KnowledgeChunk(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id"), nullable=False
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Vector embedding (pgvector)
    # Dimension matches EMBEDDING_DIMENSIONS in config (default 1536 for text-embedding-3-small)
    embedding = mapped_column(
        Vector(1536) if Vector else Text,
        nullable=True,
    )

    # Metadata (section header, page number, etc.)
    meta_data: Mapped[Optional[dict]] = mapped_column(
        MutableDict.as_mutable(JSONB),
        default=dict,
    )

    # Relationships
    document = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        Index("ix_knowledge_chunks_document", "document_id", "chunk_index"),
    )

    def __repr__(self):
        return f"<KnowledgeChunk doc={self.document_id} idx={self.chunk_index}>"
