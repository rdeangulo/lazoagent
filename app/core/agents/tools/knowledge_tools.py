"""
Lazo Agent — Knowledge Base Tools

RAG tool that searches the vector store. This is the default
tool available to all agents.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool


@tool
async def search_knowledge_base(
    query: str,
    doc_type: Optional[str] = None,
    limit: int = 5,
) -> str:
    """Search the knowledge base for information relevant to the user's question.

    Use this tool to find answers about products, policies, procedures,
    FAQs, and any other documented information.

    Args:
        query: The search query based on what the user is asking
        doc_type: Optional filter by document type (faq, policy, product, guide, general)
        limit: Maximum number of results to return
    """
    from app.services.knowledge_service import knowledge_service

    results = await knowledge_service.search(
        query=query,
        doc_type=doc_type,
        limit=limit,
    )

    if not results:
        return "No relevant information found in the knowledge base for this query."

    formatted = []
    for i, result in enumerate(results, 1):
        source = result.get("document_title", "Unknown")
        content = result.get("content", "")
        score = result.get("score", 0)
        formatted.append(f"[{i}] (source: {source}, relevance: {score:.2f})\n{content}")

    return "\n\n---\n\n".join(formatted)
