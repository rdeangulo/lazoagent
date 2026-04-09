"""Lazo Agent — Escalation Schemas"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EscalationResponse(BaseModel):
    id: str
    thread_id: str
    status: str
    priority: str
    reason: Optional[str] = None
    conversation_summary: Optional[str] = None
    assigned_operator_id: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None


class ResolveEscalationRequest(BaseModel):
    resolution_note: str
