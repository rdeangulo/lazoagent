"""Lazo Agent — Auth Schemas"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    operator: OperatorInfo


class OperatorInfo(BaseModel):
    id: str
    name: str
    email: str
    role: str
    status: str


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "agent"


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# Fix forward reference
LoginResponse.model_rebuild()
