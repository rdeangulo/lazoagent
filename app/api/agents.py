"""Lazo Agent — Agent Management Routes"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.security import get_current_admin
from app.services.agent_service import agent_service

router = APIRouter()


class CreateAgentRequest(BaseModel):
    name: str
    slug: str
    system_prompt: str
    description: Optional[str] = None
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    temperature: float = 0.3
    enabled_tools: Optional[list[str]] = None
    default_language: str = "es"


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None
    enabled_tools: Optional[list[str]] = None
    default_language: Optional[str] = None
    langfuse_prompt_name: Optional[str] = None
    knowledge_doc_types: Optional[list[str]] = None
    knowledge_search_limit: Optional[int] = None
    config: Optional[dict] = None


@router.get("")
async def list_agents(
    status: Optional[str] = Query(None),
    admin: dict = Depends(get_current_admin),
):
    return {"agents": await agent_service.list_agents(status)}


@router.post("")
async def create_agent(
    request: CreateAgentRequest,
    admin: dict = Depends(get_current_admin),
):
    return await agent_service.create_agent(**request.model_dump())


@router.get("/{agent_id}")
async def get_agent(agent_id: str, admin: dict = Depends(get_current_admin)):
    agent = await agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    admin: dict = Depends(get_current_admin),
):
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    return await agent_service.update_agent(agent_id, **updates)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, admin: dict = Depends(get_current_admin)):
    await agent_service.delete_agent(agent_id)
    return {"deleted": True}
