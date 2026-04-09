"""
Lazo Agent — LangGraph Definition

Defines the conversation graph:

    START → agent → [tools → agent]* → END

Simple but powerful: the agent decides when to use tools
and when to respond directly. Tools loop back to the agent
so it can process results and decide next steps.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.core.agents.nodes import agent_node, should_continue, tool_node
from app.core.agents.state import AgentState

logger = logging.getLogger(__name__)

_graph = None
_graph_lock = asyncio.Lock()


def _build_graph() -> StateGraph:
    """Build the LangGraph conversation graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    # Set entry point
    graph.set_entry_point("agent")

    # Add edges
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        },
    )
    graph.add_edge("tools", "agent")  # After tools, always go back to agent

    return graph


async def get_graph():
    """Get the compiled graph singleton.

    Lazy initialization with async lock to prevent race conditions
    in multi-worker environments.
    """
    global _graph

    if _graph is not None:
        return _graph

    async with _graph_lock:
        if _graph is not None:
            return _graph

        builder = _build_graph()

        # Use memory checkpointer for conversation persistence
        # In production, swap to PostgresSaver for durable state
        checkpointer = MemorySaver()

        _graph = builder.compile(checkpointer=checkpointer)
        logger.info("LangGraph compiled successfully")
        return _graph
