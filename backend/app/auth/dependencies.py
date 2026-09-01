"""
FastAPI dependencies for authentication and authorization.

`get_current_user` answers "who is calling?"; `require_admin` answers "are they
allowed?". Both read the user from the database rather than trusting claims in
the token.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_token
from app.core.errors import AuthError, PermissionError_
from app.db import get_db
from app.models.user import User, UserRole

# auto_error=False so a missing header reaches our handler and returns the same
# JSON error shape as everything else.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the caller from the `Authorization: Bearer <jwt>` header."""
    if credentials is None or not credentials.credentials:
        raise AuthError("Not authenticated.")

    claims = decode_token(credentials.credentials)
    if claims is None:
        raise AuthError("Invalid or expired token.")

    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None:
        # Token is validly signed but the account is gone.
        raise AuthError("Invalid or expired token.")
    if not user.is_active:
        raise AuthError("This account has been disabled.")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: CurrentUser) -> User:
    """Allow only admins through. 403 for an authenticated non-admin."""
    if current_user.role != UserRole.ADMIN:
        raise PermissionError_("Administrator access required.")
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
