"""Lazo Agent — API Key Management Routes"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_admin

router = APIRouter()


class CreateApiKeyRequest(BaseModel):
    name: str
    description: Optional[str] = None
    agent_ids: Optional[list[str]] = None  # null = access to all agents


@router.post("")
async def create_api_key(
    request: CreateApiKeyRequest,
    admin: dict = Depends(get_current_admin),
):
    """Create a new API key. The key is returned ONCE — store it securely."""
    from app.core.database import get_db_context
    from app.models import ApiKey

    raw_key = ApiKey.generate_key()

    async with get_db_context() as db:
        api_key = ApiKey(
            name=request.name,
            description=request.description,
            key_prefix=ApiKey.get_prefix(raw_key),
            key_hash=ApiKey.hash_key(raw_key),
            agent_ids=request.agent_ids,
        )
        db.add(api_key)
        await db.flush()

        return {
            "id": str(api_key.id),
            "key": raw_key,  # Only shown once!
            "name": api_key.name,
            "prefix": api_key.key_prefix,
            "agent_ids": api_key.agent_ids,
            "message": "Store this key securely — it will not be shown again.",
        }


@router.get("")
async def list_api_keys(admin: dict = Depends(get_current_admin)):
    """List all API keys (without the actual key)."""
    from app.core.database import get_db_context
    from app.models import ApiKey
    from sqlalchemy import select

    async with get_db_context() as db:
        result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
        keys = result.scalars().all()

        return {
            "api_keys": [
                {
                    "id": str(k.id),
                    "name": k.name,
                    "prefix": k.key_prefix,
                    "is_active": k.is_active,
                    "agent_ids": k.agent_ids,
                    "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                    "created_at": k.created_at.isoformat(),
                }
                for k in keys
            ]
        }


@router.delete("/{key_id}")
async def revoke_api_key(key_id: str, admin: dict = Depends(get_current_admin)):
    """Revoke an API key."""
    from app.core.database import get_db_context
    from app.models import ApiKey
    from sqlalchemy import select

    async with get_db_context() as db:
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        key = result.scalar_one_or_none()
        if not key:
            raise HTTPException(status_code=404, detail="API key not found")
        key.is_active = False

    return {"revoked": True}
