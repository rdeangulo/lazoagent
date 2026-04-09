"""
Lazo Agent — Prompt Registry

Composes system prompts with dynamic context injection.
Simplified: the base prompt comes from the Agent model,
with optional Langfuse override.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Prompt injection patterns
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a?", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
]


def _sanitize_value(value: str, max_length: int = 500) -> str:
    value = value[:max_length]
    value = re.sub(r"\s+", " ", value).strip()
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(value):
            return "[REDACTED]"
    return value


async def _load_langfuse_prompt(name: str) -> Optional[str]:
    if not settings.LANGFUSE_SECRET_KEY:
        return None
    try:
        from langfuse import Langfuse
        client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        prompt = client.get_prompt(name, label="production", cache_ttl_seconds=60)
        return prompt.prompt if hasattr(prompt, "prompt") else str(prompt)
    except Exception as e:
        logger.warning("Failed to load Langfuse prompt '%s': %s", name, e)
        return None


async def build_system_prompt(
    base_prompt: str = "You are a helpful AI assistant.",
    language: str = "es",
    langfuse_prompt_name: Optional[str] = None,
    additional_context: Optional[str] = None,
) -> str:
    """Build the complete system prompt.

    Priority: Langfuse prompt > base_prompt from Agent model.
    """
    # Try Langfuse first
    if langfuse_prompt_name:
        langfuse = await _load_langfuse_prompt(langfuse_prompt_name)
        if langfuse:
            base_prompt = langfuse

    # Dynamic context
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    context_parts = [
        f"Current datetime: {now}",
        f"Language: {language}",
    ]
    if additional_context:
        context_parts.append(f"Context: {_sanitize_value(additional_context, 1000)}")

    context_block = "\n".join(context_parts)
    return f"{base_prompt}\n\n---\n\n## Session Context\n{context_block}"
