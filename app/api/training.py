"""Lazo Agent — Training / Playground Routes"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_admin
from app.services.training_service import training_service

router = APIRouter()


class CreateSessionRequest(BaseModel):
    agent_id: str
    title: Optional[str] = None


class SendMessageRequest(BaseModel):
    message: str


class RateSessionRequest(BaseModel):
    rating: int  # 1-5
    notes: Optional[str] = None


@router.post("/sessions")
async def create_session(
    request: CreateSessionRequest,
    admin: dict = Depends(get_current_admin),
):
    """Create a new training/test session for an agent."""
    return await training_service.create_session(request.agent_id, request.title)


@router.get("/sessions")
async def list_sessions(
    agent_id: Optional[str] = None,
    admin: dict = Depends(get_current_admin),
):
    """List training sessions."""
    return {"sessions": await training_service.list_sessions(agent_id)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, admin: dict = Depends(get_current_admin)):
    session = await training_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/message")
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    admin: dict = Depends(get_current_admin),
):
    """Send a test message in a training session. Returns AI response."""
    return await training_service.send_message(session_id, request.message)


@router.post("/sessions/{session_id}/rate")
async def rate_session(
    session_id: str,
    request: RateSessionRequest,
    admin: dict = Depends(get_current_admin),
):
    """Rate a training session (1-5) with optional feedback."""
    return await training_service.rate_session(session_id, request.rating, request.notes)
