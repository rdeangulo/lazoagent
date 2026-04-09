"""Lazo Agent — Inbox Schemas"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InboxItemResponse(BaseModel):
    id: str
    thread_id: Optional[str] = None
    status: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_name: Optional[str] = None
    subject: Optional[str] = None
    conversation_summary: Optional[str] = None
    customer_message: Optional[str] = None
    sla_deadline: Optional[datetime] = None
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    created_at: datetime
    assigned_operator_id: Optional[str] = None


class InboxListResponse(BaseModel):
    items: list[InboxItemResponse]
    total: int
    limit: int
    offset: int


class AssignInboxRequest(BaseModel):
    operator_id: str


class ResolveInboxRequest(BaseModel):
    resolution_note: str
