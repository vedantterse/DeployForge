"""
Authentication business logic.

Route handlers stay thin: they parse input, call these functions, and return a
schema. Everything that decides *whether* a signup or login succeeds lives here.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password, verify_password
from app.core.errors import AuthError, ConflictError
from app.models.user import User, UserRole


def _normalize_email(email: str) -> str:
    """Emails are matched case-insensitively; store them lowercased."""
    return email.strip().lower()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(func.lower(User.email) == _normalize_email(email))
    )
    return result.scalar_one_or_none()


async def signup(
    db: AsyncSession,
    email: str,
    password: str,
    role: UserRole = UserRole.USER,
) -> User:
    """
    Create a new account.

    New accounts are always plain users. Admins are minted deliberately via
    `scripts/create_admin.py`, so there is no path to privilege through the
    public signup endpoint.
    """
    if await get_user_by_email(db, email) is not None:
        raise ConflictError("An account with that email already exists.")

    user = User(
        email=_normalize_email(email),
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    """
    Return the user if the credentials are valid, else raise AuthError.

    A wrong password and an unknown email produce the same error, so the
    endpoint cannot be used to discover which emails have accounts.
    """
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("Incorrect email or password.")
    if not user.is_active:
        raise AuthError("This account has been disabled.")
    return user
