"""
Lazo Agent — Application Configuration

Central configuration using pydantic-settings v2.
All values are read from environment variables with sensible defaults.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    APP_NAME: str = "Lazo Agent"
    APP_ENV: str = "development"  # development | staging | production
    LOG_LEVEL: str = "INFO"
    PORT: int = 3000
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://lazo:lazo@localhost:5432/lazoagent"
    DATABASE_URL_SYNC: str = "postgresql://lazo:lazo@localhost:5432/lazoagent"
    ANALYTICS_DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security ─────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 480
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── AI Providers ─────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4.1-mini"

    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536

    # ── Langfuse ─────────────────────────────────────────────────────────
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # ── Shopify ──────────────────────────────────────────────────────────
    SHOPIFY_STORE_URL: Optional[str] = None
    SHOPIFY_ACCESS_TOKEN: Optional[str] = None
    SHOPIFY_API_VERSION: str = "2024-10"
    SHOPIFY_WEBHOOK_SECRET: Optional[str] = None

    # ── Twilio ───────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_WHATSAPP_NUMBER: Optional[str] = None

    # ── Meta (Facebook / Instagram / WhatsApp Cloud API) ─────────────────
    META_APP_SECRET: Optional[str] = None
    META_PAGE_ACCESS_TOKEN: Optional[str] = None
    META_VERIFY_TOKEN: str = "lazo-verify-token"
    META_WHATSAPP_PHONE_ID: Optional[str] = None
    META_WHATSAPP_TOKEN: Optional[str] = None

    # ── B2Chat (Historical Knowledge Import) ───────────────────────────────
    B2CHAT_CLIENT_ID: Optional[str] = None
    B2CHAT_CLIENT_SECRET: Optional[str] = None

    # ── Email (SMTP / IMAP) ──────────────────────────────────────────────
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    IMAP_HOST: Optional[str] = None
    IMAP_PORT: int = 993

    # ── Sentry ───────────────────────────────────────────────────────────
    SENTRY_DSN: Optional[str] = None

    # ── Business Rules ───────────────────────────────────────────────────
    INBOX_AUTO_REPLY: bool = True
    INBOX_SLA_MINUTES: int = 120
    THREAD_INACTIVITY_TIMEOUT: int = 180  # minutes

    # ── Channel Map ──────────────────────────────────────────────────────
    # Maps channel slugs to their Twilio phone numbers (env var names)
    # Example: {"lazo-whatsapp": "+14155238886"}
    WHATSAPP_CHANNEL_MAP: dict[str, str] = {}

    @field_validator("WHATSAPP_CHANNEL_MAP", mode="before")
    @classmethod
    def parse_channel_map(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v) if v else {}
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
