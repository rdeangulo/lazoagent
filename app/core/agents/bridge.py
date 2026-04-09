"""
Lazo Agent — Bridge

Single entry point for processing messages through an agent.
Now agent-config-driven: each call specifies which agent to use.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from langchain_core.messages import HumanMessage

from app.core.agents.graph import get_graph

logger = logging.getLogger(__name__)

# Circuit breaker state
_failure_count: int = 0
_circuit_open_until: float = 0
_FAILURE_THRESHOLD = 5
_RESET_TIMEOUT = 60


def _check_circuit() -> bool:
    if _failure_count >= _FAILURE_THRESHOLD and time.time() < _circuit_open_until:
        return True
    return False


def _record_success():
    global _failure_count, _circuit_open_until
    _failure_count = 0
    _circuit_open_until = 0


def _record_failure():
    global _failure_count, _circuit_open_until
    _failure_count += 1
    if _failure_count >= _FAILURE_THRESHOLD:
        _circuit_open_until = time.time() + _RESET_TIMEOUT
        logger.error("Circuit breaker OPEN — %d failures", _failure_count)


async def process_message(
    message: str,
    agent_config: dict,
    thread_id: str = "default",
    language: str = "es",
    context: Optional[dict] = None,
) -> dict:
    """Process a message through an agent.

    Args:
        message: User message text
        agent_config: Agent configuration dict with:
            - system_prompt, llm_provider, llm_model, enabled_tools,
            - temperature, max_tokens, langfuse_prompt_name, etc.
        thread_id: Conversation thread ID for memory
        language: ISO language code
        context: Additional context to pass to the agent

    Returns:
        dict with: response, tool_calls, error
    """
    if _check_circuit():
        return {
            "response": "I'm experiencing technical difficulties. Please try again shortly.",
            "tool_calls": [],
            "error": "circuit_breaker_open",
        }

    try:
        graph = await get_graph()

        # Merge agent config into metadata
        meta = context or {}
        meta["agent_config"] = agent_config

        input_state = {
            "messages": [HumanMessage(content=message)],
            "thread_id": thread_id,
            "channel": "api",
            "language": language,
            "customer_id": None,
            "customer_name": None,
            "customer_email": None,
            "customer_phone": None,
            "intent": None,
            "meta_data": meta,
            "audit_events": [],
        }

        config = {"configurable": {"thread_id": thread_id}}

        # Langfuse callbacks
        callbacks = _get_langfuse_callbacks(thread_id, agent_config.get("agent_id", ""))
        if callbacks:
            config["callbacks"] = callbacks

        result = await graph.ainvoke(input_state, config=config)

        # Extract response
        ai_messages = [
            m for m in result["messages"]
            if hasattr(m, "content") and m.type == "ai" and m.content
        ]
        response_text = ai_messages[-1].content if ai_messages else ""

        tool_calls = []
        for m in result["messages"]:
            if hasattr(m, "tool_calls") and m.tool_calls:
                tool_calls.extend(m.tool_calls)

        _record_success()

        return {
            "response": response_text,
            "tool_calls": [{"name": t["name"], "args": t.get("args", {})} for t in tool_calls],
            "error": None,
        }

    except Exception as e:
        _record_failure()
        logger.exception("Error processing message: %s", e)
        return {
            "response": "I apologize, I had trouble processing your request.",
            "tool_calls": [],
            "error": str(e),
        }


def _get_langfuse_callbacks(thread_id: str, agent_id: str) -> list:
    from app.config import settings
    if not settings.LANGFUSE_SECRET_KEY:
        return []
    try:
        from langfuse.callback import CallbackHandler
        return [CallbackHandler(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
            session_id=thread_id,
            metadata={"agent_id": agent_id},
        )]
    except Exception:
        return []
