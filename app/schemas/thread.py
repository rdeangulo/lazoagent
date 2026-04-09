"""Lazo Agent — Thread & Message Schemas"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MessageCreate(BaseModel):
    content: str
    content_type: str = "text"
    sender_type: str = "customer"
    media_url: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    sender_type: str
    content: str
    content_type: str
    created_at: datetime
    media_url: Optional[str] = None
    operator_id: Optional[str] = None


class ThreadResponse(BaseModel):
    id: str
    status: str
    channel_id: Optional[str] = None
    customer_id: Optional[str] = None
    operator_id: Optional[str] = None
    subject: Optional[str] = None
    language: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = []


class ThreadListResponse(BaseModel):
    threads: list[ThreadResponse]
    total: int
    limit: int
    offset: int
