"""
Lazo Agent — LLM Factory

Multi-provider LLM initialization with per-role configuration.
Supports Anthropic (primary) and OpenAI (fallback/router).
Instances are cached per role+provider combo.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from langchain_core.language_models import BaseChatModel

from app.config import settings

logger = logging.getLogger(__name__)

# Role-to-model mapping — auto-selects based on available API keys
_agent_provider = "anthropic" if settings.ANTHROPIC_API_KEY else "openai"
_agent_model = settings.ANTHROPIC_MODEL if settings.ANTHROPIC_API_KEY else settings.OPENAI_MODEL

_ROLE_MODELS = {
    "agent": {
        "provider": _agent_provider,
        "model": _agent_model,
    },
    "router": {
        "provider": "openai",
        "model": settings.OPENAI_MODEL,
    },
}


@lru_cache(maxsize=10)
def get_llm(
    role: str = "agent",
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> BaseChatModel:
    """Get an LLM instance for the given role.

    Args:
        role: The agent role (agent, router)
        provider: Override provider (anthropic, openai)
        model: Override model name

    Returns:
        A configured LangChain chat model
    """
    config = _ROLE_MODELS.get(role, _ROLE_MODELS["agent"])
    provider = provider or config["provider"]
    model_name = model or config["model"]

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=4096,
            temperature=0.3,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=4096,
            temperature=0.3,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def get_embedding_model():
    """Get the embedding model for vector store operations."""
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
        dimensions=settings.EMBEDDING_DIMENSIONS,
    )
