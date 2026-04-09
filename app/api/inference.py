"""Lazo Agent — Inference API (External Services)

This is the main integration point. External CRMs and services
call POST /v1/chat to send a customer message and get an AI response.

Authenticated via API key (X-API-Key header).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_api_key_record
from app.services.agent_service import agent_service

router = APIRouter()


class ChatRequest(BaseModel):
    agent_id: Optional[str] = None   # Agent UUID (use this or agent_slug)
    agent_slug: Optional[str] = None  # Agent slug (alternative to agent_id)
    message: str                       # Customer message
    thread_id: str = "default"         # Conversation thread for memory
    language: str = "es"               # ISO language code
    context: Optional[dict] = None     # Additional context passed to agent


class ChatResponse(BaseModel):
    response: str                          # AI response text
    tool_calls: list[dict] = []           # Tools the AI used
    agent_id: str                          # Which agent handled it
    thread_id: str                         # Thread ID for continuity
    error: Optional[str] = None           # Error if any


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    api_key: dict = Depends(get_api_key_record),
):
    """Send a message to an AI agent and get a response.

    Authenticate with X-API-Key header. Specify agent by ID or slug.
    Use thread_id for multi-turn conversations (same thread_id = same context).
    """
    # Resolve agent
    agent = None
    if request.agent_id:
        agent = await agent_service.get_agent(request.agent_id)
    elif request.agent_slug:
        agent = await agent_service.get_agent_by_slug(request.agent_slug)
    else:
        raise HTTPException(status_code=400, detail="Provide agent_id or agent_slug")

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check API key has access to this agent
    allowed_agents = api_key.get("agent_ids", [])
    if allowed_agents and agent["id"] not in allowed_agents:
        raise HTTPException(status_code=403, detail="API key does not have access to this agent")

    # Check agent is active
    if agent["status"] != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Agent is {agent['status']}. Only active agents accept messages.",
        )

    # Process message
    from app.core.agents.bridge import process_message

    agent_config = agent_service.get_agent_config(agent)
    result = await process_message(
        message=request.message,
        agent_config=agent_config,
        thread_id=request.thread_id,
        language=request.language,
        context=request.context,
    )

    return ChatResponse(
        response=result["response"],
        tool_calls=result.get("tool_calls", []),
        agent_id=agent["id"],
        thread_id=request.thread_id,
        error=result.get("error"),
    )
