"""
Lazo Agent — Graph Nodes

Agent-config-driven: reads persona, tools, and LLM settings
from the Agent model instead of hardcoded config.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import SystemMessage

from app.core.agents.state import AgentState, sanitize_messages
from app.core.agents.tools.knowledge_tools import search_knowledge_base
from app.core.agents.tools.common_tools import thread_complete

logger = logging.getLogger(__name__)

# Registry of all available tools
TOOL_REGISTRY = {
    "search_knowledge_base": search_knowledge_base,
    "thread_complete": thread_complete,
}

# Default tools if agent config doesn't specify
DEFAULT_TOOLS = [search_knowledge_base, thread_complete]


def get_tools_for_agent(agent_config: dict) -> list:
    """Resolve tool objects from agent's enabled_tools list."""
    enabled = agent_config.get("enabled_tools")
    if not enabled:
        return DEFAULT_TOOLS

    tools = []
    for name in enabled:
        tool = TOOL_REGISTRY.get(name)
        if tool:
            tools.append(tool)
    return tools or DEFAULT_TOOLS


async def agent_node(state: AgentState) -> dict[str, Any]:
    """Main agent node — reads config from state.meta_data['agent_config']."""
    agent_config = state.get("meta_data", {}).get("agent_config", {})

    # Build system prompt from agent config
    system_prompt = agent_config.get("system_prompt", "You are a helpful AI assistant.")

    # Inject dynamic context
    from app.core.agents.prompt_registry import build_system_prompt
    system_prompt = await build_system_prompt(
        base_prompt=system_prompt,
        language=state.get("language", "es"),
        additional_context=agent_config.get("additional_context"),
    )

    # Get LLM configured for this agent
    from app.core.agents.llm import get_llm
    llm = get_llm(
        role="agent",
        provider=agent_config.get("llm_provider"),
        model=agent_config.get("llm_model"),
    )

    # Get tools for this agent
    tools = get_tools_for_agent(agent_config)
    llm_with_tools = llm.bind_tools(tools)

    # Sanitize messages
    messages = sanitize_messages(state["messages"])
    full_messages = [SystemMessage(content=system_prompt)] + messages

    # Invoke
    response = await llm_with_tools.ainvoke(full_messages)
    return {"messages": [response]}


async def tool_node(state: AgentState) -> dict[str, Any]:
    """Execute tool calls — uses tools from agent config."""
    from langgraph.prebuilt import ToolNode

    agent_config = state.get("meta_data", {}).get("agent_config", {})
    tools = get_tools_for_agent(agent_config)

    executor = ToolNode(tools)
    return await executor.ainvoke(state)


def should_continue(state: AgentState) -> str:
    """Route: tools or end."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"
