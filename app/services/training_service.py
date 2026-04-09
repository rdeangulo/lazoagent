"""
Lazo Agent — Training Service

Test playground: run conversations against an agent,
track quality, and store results.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.core.agents.bridge import process_message
from app.services.agent_service import agent_service

logger = logging.getLogger(__name__)


class TrainingService:

    async def create_session(self, agent_id: str, title: Optional[str] = None) -> dict:
        from app.core.database import get_db_context
        from app.models import TrainingSession

        async with get_db_context() as db:
            session = TrainingSession(
                agent_id=agent_id,
                title=title or f"Test session {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
                messages=[],
            )
            db.add(session)
            await db.flush()
            return self._format(session)

    async def send_message(self, session_id: str, message: str) -> dict:
        """Send a test message in a training session. Returns AI response."""
        from app.core.database import get_db_context
        from app.models import TrainingSession
        from sqlalchemy import select

        # Load session
        async with get_db_context() as db:
            result = await db.execute(
                select(TrainingSession).where(TrainingSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            agent_id = str(session.agent_id)

        # Load agent config
        agent = await agent_service.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        agent_config = agent_service.get_agent_config(agent)

        # Process through the agent
        result = await process_message(
            message=message,
            agent_config=agent_config,
            thread_id=f"training-{session_id}",
            language=agent.get("default_language", "es"),
        )

        # Record in session
        now = datetime.now(timezone.utc).isoformat()
        user_msg = {"role": "user", "content": message, "timestamp": now}
        assistant_msg = {
            "role": "assistant",
            "content": result["response"],
            "timestamp": now,
            "tool_calls": result.get("tool_calls", []),
            "error": result.get("error"),
        }

        async with get_db_context() as db:
            stmt_result = await db.execute(
                select(TrainingSession).where(TrainingSession.id == session_id)
            )
            session = stmt_result.scalar_one()

            msgs = list(session.messages or [])
            msgs.extend([user_msg, assistant_msg])
            session.messages = msgs
            session.message_count = len([m for m in msgs if m["role"] == "user"])
            session.tool_call_count = sum(
                len(m.get("tool_calls", [])) for m in msgs if m["role"] == "assistant"
            )
            session.knowledge_hits = sum(
                1 for m in msgs
                if m["role"] == "assistant"
                for t in m.get("tool_calls", [])
                if t.get("name") == "search_knowledge_base"
            )

        return {
            "user_message": message,
            "ai_response": result["response"],
            "tool_calls": result.get("tool_calls", []),
            "error": result.get("error"),
        }

    async def get_session(self, session_id: str) -> Optional[dict]:
        from app.core.database import get_db_context
        from app.models import TrainingSession
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(
                select(TrainingSession).where(TrainingSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            return self._format(session) if session else None

    async def list_sessions(self, agent_id: Optional[str] = None) -> list[dict]:
        from app.core.database import get_db_context
        from app.models import TrainingSession
        from sqlalchemy import select

        async with get_db_context() as db:
            stmt = select(TrainingSession).order_by(TrainingSession.created_at.desc())
            if agent_id:
                stmt = stmt.where(TrainingSession.agent_id == agent_id)
            result = await db.execute(stmt)
            return [self._format(s) for s in result.scalars().all()]

    async def rate_session(self, session_id: str, rating: int, notes: Optional[str] = None) -> dict:
        from app.core.database import get_db_context
        from app.models import TrainingSession
        from app.models.training import SessionStatus
        from sqlalchemy import select

        async with get_db_context() as db:
            result = await db.execute(
                select(TrainingSession).where(TrainingSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                raise ValueError(f"Session {session_id} not found")

            session.rating = min(max(rating, 1), 5)
            session.feedback_notes = notes
            session.status = SessionStatus.COMPLETED

            return self._format(session)

    def _format(self, session) -> dict:
        return {
            "id": str(session.id),
            "agent_id": str(session.agent_id),
            "title": session.title,
            "status": session.status.value,
            "messages": session.messages or [],
            "message_count": session.message_count,
            "tool_call_count": session.tool_call_count,
            "knowledge_hits": session.knowledge_hits,
            "rating": session.rating,
            "feedback_notes": session.feedback_notes,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }


training_service = TrainingService()
