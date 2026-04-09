"""Lazo Agent — Authentication Routes"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_operator, hash_password
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.operator_service import operator_service

router = APIRouter()


@router.post("/login")
async def login(request: LoginRequest, response: Response):
    """Authenticate operator and return JWT token."""
    try:
        result = await operator_service.login(request.email, request.password)

        # Set httponly cookie
        response.set_cookie(
            key="access_token",
            value=result["access_token"],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=60 * 60 * 8,  # 8 hours
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
async def logout(
    response: Response,
    operator: dict = Depends(get_current_operator),
):
    """Log out operator and clear session."""
    await operator_service.logout(operator["sub"])
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.post("/register")
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    operator: dict = Depends(get_current_operator),
):
    """Register a new operator (admin only)."""
    if operator.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    from app.models import Operator
    from app.models.operator import OperatorRole

    new_operator = Operator(
        email=request.email,
        name=request.name,
        password_hash=hash_password(request.password),
        role=OperatorRole(request.role),
    )
    db.add(new_operator)
    await db.commit()

    return {"id": str(new_operator.id), "email": new_operator.email, "name": new_operator.name}


@router.get("/me")
async def get_me(operator: dict = Depends(get_current_operator)):
    """Get current operator info from JWT."""
    return operator
