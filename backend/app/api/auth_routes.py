"""App authentication routes: signup, login, and the current user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service
from app.auth.dependencies import CurrentUser
from app.auth.security import create_access_token
from app.config import settings
from app.db import get_db
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _token_response(user) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in_minutes=settings.jwt_expire_minutes,
        user=UserOut.model_validate(user),
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, db: DbSession) -> TokenResponse:
    """Create an account (always with role `user`) and log straight in."""
    user = await service.signup(db, payload.email, payload.password)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    """Exchange email + password for a JWT."""
    user = await service.authenticate(db, payload.email, payload.password)
    return _token_response(user)


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    """Return the authenticated user. 401 without a valid token."""
    return UserOut.model_validate(current_user)
