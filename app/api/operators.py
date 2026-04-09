"""Lazo Agent — Operator Management Routes"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_operator
from app.models import Operator
from app.services.operator_service import operator_service

router = APIRouter()


@router.get("")
async def list_operators(
    db: AsyncSession = Depends(get_db),
    operator: dict = Depends(get_current_operator),
):
    """List all operators (admin only)."""
    if operator.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(select(Operator).order_by(Operator.name))
    operators = result.scalars().all()

    return {
        "operators": [
            {
                "id": str(op.id),
                "name": op.name,
                "email": op.email,
                "role": op.role.value,
                "status": op.status.value,
                "last_login": op.last_login.isoformat() if op.last_login else None,
            }
            for op in operators
        ]
    }


@router.post("/status")
async def update_status(
    status: str,
    operator: dict = Depends(get_current_operator),
):
    """Update current operator's status."""
    await operator_service.update_status(operator["sub"], status)
    return {"status": status}


@router.get("/online-count")
async def online_count(operator: dict = Depends(get_current_operator)):
    """Get count of currently online operators."""
    count = await operator_service.get_online_count()
    return {"online_count": count}
