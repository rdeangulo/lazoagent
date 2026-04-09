"""Lazo Agent — Knowledge Base Schemas"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DocumentUploadRequest(BaseModel):
    title: str
    content: str
    doc_type: str = "general"
    description: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    doc_type: str
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class SearchRequest(BaseModel):
    query: str
    doc_type: Optional[str] = None
    limit: int = 5


class SearchResult(BaseModel):
    chunk_id: str
    content: str
    document_title: str
    doc_type: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
