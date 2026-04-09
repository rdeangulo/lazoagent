"""Lazo Agent — Admin Authentication Routes"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr

from app.core.security import create_access_token, get_current_admin, hash_password, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def login(request: LoginRequest, response: Response):
    """Admin login — returns JWT."""
    from app.core.database import get_db_context
    from sqlalchemy import select, text

    # Simple admin auth — check against a config table or env
    # For now, using hardcoded check (replace with proper admin model later)
    from app.config import settings

    # Check if there's an admin record in the database
    async with get_db_context() as db:
        result = await db.execute(text(
            "SELECT id, email, name, password_hash FROM admins WHERE email = :email"
        ), {"email": request.email})
        admin = result.first()

    if not admin or not verify_password(request.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({
        "sub": str(admin.id),
        "email": admin.email,
        "name": admin.name,
    })

    response.set_cookie(
        key="access_token", value=token,
        httponly=True, secure=True, samesite="lax", max_age=60 * 60 * 8,
    )

    return {"access_token": token, "name": admin.name, "email": admin.email}


@router.post("/logout")
async def logout(response: Response, admin: dict = Depends(get_current_admin)):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me")
async def get_me(admin: dict = Depends(get_current_admin)):
    return admin
