"""
Lazo Agent — Bridge

The single entry point for processing customer messages through
the LangGraph agent. All channels (WhatsApp, web, Facebook, etc.)
call this function.

Handles:
- Context extraction from thread metadata
- Langfuse callback handler for observability
- Circuit breaker protection
- Auto-escalation on unrecoverable errors
- Thread metadata updates
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from langchain_core.messages import HumanMessage

from app.core.agents.graph import get_graph
from app.core.agents.state import AgentState, create_initial_state

logger = logging.getLogger(__name__)

# ── Circuit Breaker ──────────────────────────────────────────────────────────

_failure_count: int = 0
_circuit_open_until: float = 0
_FAILURE_THRESHOLD = 5
_RESET_TIMEOUT = 60  # seconds
_MAX_RETRIES = 3


def _check_circuit_breaker() -> bool:
    """Returns True if the circuit is open (should NOT proceed)."""
    global _circuit_open_until
    if _failure_count >= _FAILURE_THRESHOLD:
        if time.time() < _circuit_open_until:
            return True
        # Half-open: allow one attempt
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
        logger.error("Circuit breaker OPEN — %d consecutive failures", _failure_count)


# ── Main Entry Point ─────────────────────────────────────────────────────────


async def process_message(
    message: str,
    thread_id: str,
    channel: str = "web_chat",
    language: str = "es",
    customer_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_email: Optional[str] = None,
    customer_phone: Optional[str] = None,
    meta_data: Optional[dict] = None,
) -> dict:
    """Process a customer message through the LangGraph agent.

    Args:
        message: The customer's message text
        thread_id: Unique thread identifier
        channel: Channel slug (whatsapp, web_chat, facebook, etc.)
        language: ISO language code
        customer_id: Database customer ID
        customer_name: Customer name for personalization
        customer_email: Customer email for order lookups
        customer_phone: Customer phone
        meta_data: Additional context to pass to the agent

    Returns:
        dict with keys:
            - response: The AI's response text
            - tool_calls: List of tools that were called
            - error: Error message if something went wrong
    """
    # Check circuit breaker
    if _check_circuit_breaker():
        logger.warning("Circuit breaker OPEN — auto-escalating thread %s", thread_id)
        return {
            "response": (
                "I'm experiencing some technical difficulties right now. "
                "Let me connect you with a team member who can help."
            ),
            "tool_calls": [],
            "error": "circuit_breaker_open",
            "should_escalate": True,
        }

    try:
        graph = await get_graph()

        # Create the input state with the customer message
        input_state = {
            "messages": [HumanMessage(content=message)],
            "thread_id": thread_id,
            "channel": channel,
            "language": language,
            "customer_id": customer_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": customer_phone,
            "intent": None,
            "meta_data": meta_data or {},
            "audit_events": [],
        }

        # Config with thread_id for checkpointer
        config = {
            "configurable": {"thread_id": thread_id},
        }

        # Add Langfuse callbacks if available
        callbacks = _get_langfuse_callbacks(thread_id, channel)
        if callbacks:
            config["callbacks"] = callbacks

        # Invoke the graph
        result = await graph.ainvoke(input_state, config=config)

        # Extract the final AI response
        ai_messages = [
            m for m in result["messages"]
            if hasattr(m, "content") and m.type == "ai" and m.content
        ]
        response_text = ai_messages[-1].content if ai_messages else ""

        # Collect tool calls for audit
        tool_calls = []
        for m in result["messages"]:
            if hasattr(m, "tool_calls") and m.tool_calls:
                tool_calls.extend(m.tool_calls)

        _record_success()

        return {
            "response": response_text,
            "tool_calls": tool_calls,
            "error": None,
            "should_escalate": False,
        }

    except Exception as e:
        _record_failure()
        logger.exception("Error processing message in thread %s: %s", thread_id, e)

        return {
            "response": (
                "I apologize, but I'm having trouble processing your request. "
                "Let me connect you with a team member."
            ),
            "tool_calls": [],
            "error": str(e),
            "should_escalate": True,
        }


def _get_langfuse_callbacks(thread_id: str, channel: str) -> list:
    """Create Langfuse callback handlers if configured."""
    from app.config import settings

    if not settings.LANGFUSE_SECRET_KEY:
        return []

    try:
        from langfuse.callback import CallbackHandler

        return [
            CallbackHandler(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST,
                session_id=thread_id,
                metadata={"channel": channel},
            )
        ]
    except Exception as e:
        logger.warning("Failed to create Langfuse callback: %s", e)
        return []
