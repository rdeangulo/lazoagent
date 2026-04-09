"""
Lazo Agent — LangGraph State Definition

The agent state flows through the graph, accumulating messages
and context as the conversation progresses.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class LazoAgentState:
    """TypedDict-like state for the LangGraph conversation graph.

    Using a class with annotations for LangGraph compatibility.
    """
    pass


# LangGraph state as a TypedDict
from typing import TypedDict


class AgentState(TypedDict):
    """Core state that flows through the LangGraph agent."""

    # Conversation messages (LangGraph reducer merges new messages)
    messages: Annotated[list[BaseMessage], add_messages]

    # Thread context
    thread_id: str
    channel: str
    language: str

    # Customer info
    customer_id: Optional[str]
    customer_name: Optional[str]
    customer_email: Optional[str]
    customer_phone: Optional[str]

    # Agent routing
    intent: Optional[str]  # general, order_status, escalation

    # Metadata
    meta_data: dict[str, Any]

    # Audit trail for tool calls
    audit_events: list[dict]


def create_initial_state(
    thread_id: str,
    channel: str = "web_chat",
    language: str = "es",
    customer_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_email: Optional[str] = None,
    customer_phone: Optional[str] = None,
    meta_data: Optional[dict] = None,
) -> AgentState:
    """Create the initial state for a new conversation turn."""
    return AgentState(
        messages=[],
        thread_id=thread_id,
        channel=channel,
        language=language,
        customer_id=customer_id,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        intent=None,
        meta_data=meta_data or {},
        audit_events=[],
    )


def sanitize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Remove orphaned tool_use blocks from interrupted runs.

    When a graph run is interrupted mid-tool-call, the state may contain
    AIMessages with tool_use blocks but no corresponding ToolMessages.
    This causes errors on the next invocation.
    """
    from langchain_core.messages import AIMessage, ToolMessage

    # Collect all tool call IDs that have responses
    responded_ids = set()
    for msg in messages:
        if isinstance(msg, ToolMessage):
            responded_ids.add(msg.tool_call_id)

    cleaned = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            # Filter out tool calls without responses
            remaining_calls = [
                tc for tc in msg.tool_calls if tc["id"] in responded_ids
            ]
            if remaining_calls:
                msg = msg.copy()
                msg.tool_calls = remaining_calls
                cleaned.append(msg)
            elif msg.content:
                # Keep the message text even if tool calls are stripped
                msg = msg.copy()
                msg.tool_calls = []
                cleaned.append(msg)
            # else: drop entirely
        else:
            cleaned.append(msg)

    return cleaned
