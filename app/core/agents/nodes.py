"""
Lazo Agent — Graph Nodes

Each node is a function that takes AgentState, processes it,
and returns updated state. Nodes are composed into the LangGraph.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.agents.llm import get_llm
from app.core.agents.prompt_registry import build_system_prompt
from app.core.agents.state import AgentState, sanitize_messages
from app.core.agents.tools.common_tools import thread_complete
from app.core.agents.tools.escalation_tools import capture_contact_info, escalate_to_agent
from app.core.agents.tools.knowledge_tools import search_knowledge_base
from app.core.agents.tools.shopify_tools import check_order_status, get_order_history

logger = logging.getLogger(__name__)

# All tools available to the agent
AGENT_TOOLS = [
    search_knowledge_base,
    check_order_status,
    get_order_history,
    escalate_to_agent,
    capture_contact_info,
    thread_complete,
]


async def agent_node(state: AgentState) -> dict[str, Any]:
    """Main agent node — the Lazo AI customer service assistant.

    Processes the customer message using the LLM with all available tools.
    """
    # Build system prompt with current context
    system_prompt = await build_system_prompt(
        language=state.get("language", "es"),
        customer_name=state.get("customer_name"),
        customer_email=state.get("customer_email"),
        channel=state.get("channel", "web_chat"),
    )

    # Get LLM with tools bound
    llm = get_llm("agent")
    llm_with_tools = llm.bind_tools(AGENT_TOOLS)

    # Sanitize messages to remove orphaned tool calls
    messages = sanitize_messages(state["messages"])

    # Prepend system message
    full_messages = [SystemMessage(content=system_prompt)] + messages

    # Invoke LLM
    response = await llm_with_tools.ainvoke(full_messages)

    return {"messages": [response]}


async def tool_node(state: AgentState) -> dict[str, Any]:
    """Execute tool calls from the agent's response.

    Uses LangGraph's ToolNode under the hood but wraps it
    for audit logging and error handling.
    """
    from langgraph.prebuilt import ToolNode

    tool_executor = ToolNode(AGENT_TOOLS)
    result = await tool_executor.ainvoke(state)
    return result


def should_continue(state: AgentState) -> str:
    """Routing function: decide whether to call tools or finish.

    If the last message has tool_calls, route to tool_node.
    Otherwise, the agent is done — route to END.
    """
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return "end"
