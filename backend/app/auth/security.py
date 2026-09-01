"""
Password hashing and JWT creation/validation.

Pure crypto helpers — no database, no FastAPI. `service.py` and
`dependencies.py` build on these.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# bcrypt only. `deprecated="auto"` lets us add a stronger scheme later and
# transparently re-hash on next login.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# bcrypt silently ignores anything past 72 bytes, which would mean any 72-byte
# prefix of a longer password authenticates. Requests are rejected above this
# length instead (see schemas/auth.py) so that can never happen quietly.
MAX_PASSWORD_BYTES = 72

TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    """Return a bcrypt hash of `password`. The plaintext is never stored."""
    return _pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored hash. Never raises."""
    try:
        return _pwd_context.verify(password, hashed_password)
    except Exception:  # malformed/unknown hash in the DB
        return False


def create_access_token(user_id: uuid.UUID | str) -> str:
    """
    Issue a signed JWT for `user_id`.

    The token carries identity and expiry only — deliberately not the role.
    Authorization reads the role from the database on each request, so
    promoting or demoting a user takes effect immediately instead of whenever
    their current token happens to expire.
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    """
    Validate a JWT and return its claims, or None if it is unusable.

    Returns None (rather than raising) for a bad signature, an expired token,
    a wrong token type, or a subject that is not a UUID.
    """
    try:
        claims = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None

    if claims.get("type") != TOKEN_TYPE:
        return None

    subject = claims.get("sub")
    if not subject:
        return None
    try:
        uuid.UUID(subject)
    except (ValueError, TypeError, AttributeError):
        return None

    return claims
