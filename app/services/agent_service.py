"""
Lazo Agent — Agent Service

CRUD and configuration for AI agents.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class AgentService:

    async def create_agent(
        self,
        name: str,
        slug: str,
        system_prompt: str,
        description: Optional[str] = None,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4.1-mini",
        temperature: float = 0.3,
        enabled_tools: Optional[list] = None,
        default_language: str = "es",
    ) -> dict:
        from app.core.database import get_db_context
        from app.models import Agent

        async with get_db_context() as db:
            agent = Agent(
                name=name,
                slug=slug,
                description=description,
                system_prompt=system_prompt,
                llm_provider=llm_provider,
                llm_model=llm_model,
                temperature=temperature,
                enabled_tools=enabled_tools or ["search_knowledge_base", "thread_complete"],
                default_language=default_language,
            )
            db.add(agent)
            await db.flush()
            return self._format(agent)

    async def get_agent(self, agent_id: str) -> Optional[dict]:
        from app.core.database import get_db_context
        from app.models import Agent
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            return self._format(agent) if agent else None

    async def get_agent_by_slug(self, slug: str) -> Optional[dict]:
        from app.core.database import get_db_context
        from app.models import Agent
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(select(Agent).where(Agent.slug == slug))
            agent = result.scalar_one_or_none()
            return self._format(agent) if agent else None

    async def list_agents(self, status: Optional[str] = None) -> list[dict]:
        from app.core.database import get_db_context
        from app.models import Agent
        from app.models.agent import AgentStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            stmt = select(Agent).order_by(Agent.created_at.desc())
            if status:
                stmt = stmt.where(Agent.status == AgentStatus(status))
            result = await db.execute(stmt)
            return [self._format(a) for a in result.scalars().all()]

    async def update_agent(self, agent_id: str, **updates) -> dict:
        from app.core.database import get_db_context
        from app.models import Agent
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            for key, value in updates.items():
                if hasattr(agent, key) and value is not None:
                    setattr(agent, key, value)

            return self._format(agent)

    async def delete_agent(self, agent_id: str):
        from app.core.database import get_db_context
        from app.models import Agent
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one_or_none()
            if agent:
                await db.delete(agent)

    def get_agent_config(self, agent_dict: dict) -> dict:
        """Convert agent dict to config dict for the bridge."""
        return {
            "agent_id": agent_dict["id"],
            "system_prompt": agent_dict["system_prompt"],
            "llm_provider": agent_dict["llm_provider"],
            "llm_model": agent_dict["llm_model"],
            "temperature": agent_dict["temperature"],
            "max_tokens": agent_dict["max_tokens"],
            "enabled_tools": agent_dict["enabled_tools"],
            "langfuse_prompt_name": agent_dict.get("langfuse_prompt_name"),
        }

    def _format(self, agent) -> dict:
        return {
            "id": str(agent.id),
            "name": agent.name,
            "slug": agent.slug,
            "description": agent.description,
            "status": agent.status.value,
            "system_prompt": agent.system_prompt,
            "default_language": agent.default_language,
            "llm_provider": agent.llm_provider,
            "llm_model": agent.llm_model,
            "temperature": agent.temperature,
            "max_tokens": agent.max_tokens,
            "enabled_tools": agent.enabled_tools,
            "knowledge_doc_types": agent.knowledge_doc_types,
            "knowledge_search_limit": agent.knowledge_search_limit,
            "langfuse_prompt_name": agent.langfuse_prompt_name,
            "config": agent.config,
            "created_at": agent.created_at.isoformat(),
            "updated_at": agent.updated_at.isoformat(),
        }


agent_service = AgentService()
