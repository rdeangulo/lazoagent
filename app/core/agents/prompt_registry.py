"""
Lazo Agent — Prompt Registry

Loads and composes system prompts using Langfuse for management
with local disk fallback. Prompts are layered:

1. Base prompt (from Langfuse or local file)
2. Dynamic context (datetime, language, customer info)
3. Prompt injection defense (sanitization)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

# Prompt injection patterns to detect and block
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a?", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
]

_VALID_LANGUAGES = {"es", "en", "fr", "pt", "de", "it", "zh", "ja", "ko"}


def _sanitize_value(value: str, max_length: int = 500) -> str:
    """Sanitize a dynamic value before injecting into a prompt."""
    value = value[:max_length]
    value = re.sub(r"\s+", " ", value).strip()

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(value):
            return "[REDACTED]"

    return value


def _load_local_prompt(filename: str) -> Optional[str]:
    """Load a prompt from the local prompts directory."""
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


async def _load_langfuse_prompt(name: str) -> Optional[str]:
    """Load a prompt from Langfuse with caching."""
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
    language: str = "es",
    customer_name: Optional[str] = None,
    customer_email: Optional[str] = None,
    channel: str = "web_chat",
    additional_context: Optional[str] = None,
) -> str:
    """Build the complete system prompt for the Lazo agent.

    Layers:
    1. Base prompt (Langfuse → local fallback)
    2. Dynamic context injection
    """
    # Validate language
    if language not in _VALID_LANGUAGES:
        language = "es"

    # Load base prompt
    base = await _load_langfuse_prompt("lazo-agent-base")
    if not base:
        base = _load_local_prompt("base_agent.md")
    if not base:
        base = "You are Lazo's AI customer service assistant."

    # Build dynamic context
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    context_parts = [
        f"Current datetime: {now}",
        f"Language: {language}",
        f"Channel: {channel}",
    ]

    if customer_name:
        context_parts.append(f"Customer name: {_sanitize_value(customer_name)}")
    if customer_email:
        context_parts.append(f"Customer email: {_sanitize_value(customer_email)}")
    if additional_context:
        context_parts.append(f"Additional context: {_sanitize_value(additional_context, 1000)}")

    context_block = "\n".join(context_parts)

    return f"{base}\n\n---\n\n## Current Session Context\n{context_block}"
