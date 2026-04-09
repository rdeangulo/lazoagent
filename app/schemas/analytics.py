"""Lazo Agent — Analytics Schemas"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OverviewMetrics(BaseModel):
    period: dict
    conversations: dict
    escalations: dict
    inbox: dict
    messages: dict


class ChannelBreakdown(BaseModel):
    channel: str
    type: str
    conversations: int


class DailyVolume(BaseModel):
    date: str
    conversations: int


class SLAMetrics(BaseModel):
    total: int
    pending: int
    resolved: int
    sla_breached: int
    sla_compliance_rate: float
