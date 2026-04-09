"""
Lazo Agent — Common Tools

Utility tools available to all agent nodes.
"""

from __future__ import annotations

from langchain_core.tools import tool


@tool
async def thread_complete(
    resolution_summary: str,
) -> str:
    """Mark the conversation as resolved.

    Use this when the customer's issue has been fully addressed
    and they confirm they don't need anything else.

    Args:
        resolution_summary: Brief summary of how the issue was resolved
    """
    return f"Conversation marked as resolved. Summary: {resolution_summary}"
