"""
Lazo Agent — Exception Hierarchy

Structured exceptions for clear error handling across the application.
Each domain has its own error branch for targeted catch blocks.
"""

from __future__ import annotations


class LazoError(Exception):
    """Base exception for all Lazo Agent errors."""

    def __init__(self, message: str = "", code: str = "LAZO_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


# ── Database ─────────────────────────────────────────────────────────────────


class DatabaseError(LazoError):
    def __init__(self, message: str = "Database error", code: str = "DB_ERROR"):
        super().__init__(message, code)


class DatabaseConnectionError(DatabaseError):
    def __init__(self, message: str = "Database connection failed"):
        super().__init__(message, "DB_CONNECTION_ERROR")


class NotFoundError(DatabaseError):
    def __init__(self, entity: str = "Record", identifier: str = ""):
        msg = f"{entity} not found" + (f": {identifier}" if identifier else "")
        super().__init__(msg, "NOT_FOUND")


# ── Agent / AI ───────────────────────────────────────────────────────────────


class AgentError(LazoError):
    def __init__(self, message: str = "Agent error", code: str = "AGENT_ERROR"):
        super().__init__(message, code)


class LLMError(AgentError):
    def __init__(self, message: str = "LLM call failed"):
        super().__init__(message, "LLM_ERROR")


class LLMTimeoutError(AgentError):
    def __init__(self, message: str = "LLM call timed out"):
        super().__init__(message, "LLM_TIMEOUT")


class ToolError(AgentError):
    def __init__(self, message: str = "Tool execution failed"):
        super().__init__(message, "TOOL_ERROR")


# ── Shopify ──────────────────────────────────────────────────────────────────


class ShopifyError(LazoError):
    def __init__(self, message: str = "Shopify error", code: str = "SHOPIFY_ERROR"):
        super().__init__(message, code)


class ShopifyAuthError(ShopifyError):
    def __init__(self):
        super().__init__("Shopify authentication failed", "SHOPIFY_AUTH_ERROR")


class ShopifyNotFoundError(ShopifyError):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found in Shopify", "SHOPIFY_NOT_FOUND")


# ── Messaging / Channels ────────────────────────────────────────────────────


class MessagingError(LazoError):
    def __init__(self, message: str = "Messaging error", code: str = "MSG_ERROR"):
        super().__init__(message, code)


class DeliveryError(MessagingError):
    def __init__(self, channel: str = "", detail: str = ""):
        msg = f"Failed to deliver message via {channel}" + (f": {detail}" if detail else "")
        super().__init__(msg, "DELIVERY_ERROR")


class WebhookError(MessagingError):
    def __init__(self, message: str = "Webhook processing failed"):
        super().__init__(message, "WEBHOOK_ERROR")


# ── Escalation ───────────────────────────────────────────────────────────────


class EscalationError(LazoError):
    def __init__(self, message: str = "Escalation error", code: str = "ESCALATION_ERROR"):
        super().__init__(message, code)


class NoAgentAvailableError(EscalationError):
    def __init__(self):
        super().__init__("No agents currently available", "NO_AGENT_AVAILABLE")


# ── Knowledge Base ───────────────────────────────────────────────────────────


class KnowledgeError(LazoError):
    def __init__(self, message: str = "Knowledge base error", code: str = "KB_ERROR"):
        super().__init__(message, code)


class EmbeddingError(KnowledgeError):
    def __init__(self, message: str = "Embedding generation failed"):
        super().__init__(message, "EMBEDDING_ERROR")
