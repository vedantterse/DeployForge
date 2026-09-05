"""Request/response shapes for app authentication."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.auth.security import MAX_PASSWORD_BYTES
from app.models.user import UserRole

# 8 is a floor worth enforcing; the ceiling is bcrypt's, not ours (see
# security.MAX_PASSWORD_BYTES).
PasswordField = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = PasswordField


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_BYTES)


class UserOut(BaseModel):
    """A user as the API exposes it — never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    is_active: bool
    max_deployments: int = 3
    can_deploy: bool = True
    deploy_block_reason: str | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserOut
