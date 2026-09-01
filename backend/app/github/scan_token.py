"""
Signed scan tokens.

A scan downloads a repository once and detects every candidate target. The user
then picks one — and that pick must not require a second download, nor let the
client dictate what was "detected".

The answer is the same pattern the OAuth `state` uses: hand the client a
short-lived token signed with the app secret, holding the scan result. When it
comes back, the signature proves we produced it and nobody edited it. No
server-side cache, no extra table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.config import settings
from app.core.errors import AppError

# Long enough to read the candidate list and choose; short enough that a stale
# scan cannot be replayed against a repository that has since changed.
SCAN_TTL_MINUTES = 30
_SCAN_TOKEN_TYPE = "repo_scan"


class InvalidScanTokenError(AppError):
    code = "invalid_scan"
    status_code = 400


def create_scan_token(user_id: uuid.UUID, payload: dict[str, Any]) -> str:
    """Sign a scan result for `user_id`."""
    now = datetime.now(timezone.utc)
    claims = {
        **payload,
        "sub": str(user_id),
        "type": _SCAN_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=SCAN_TTL_MINUTES),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def read_scan_token(token: str, user_id: uuid.UUID) -> dict[str, Any]:
    """
    Validate a scan token and return its claims.

    Rejects a bad signature, an expired scan, a token of another type, and — so
    one user cannot connect a repository from another user's scan — a token
    issued to a different account.
    """
    if not token:
        raise InvalidScanTokenError("Missing scan token.")
    try:
        claims = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise InvalidScanTokenError(
            "This scan has expired or is invalid. Please scan the repository again."
        ) from exc

    if claims.get("type") != _SCAN_TOKEN_TYPE:
        raise InvalidScanTokenError("Invalid scan token.")
    if claims.get("sub") != str(user_id):
        raise InvalidScanTokenError("This scan belongs to a different account.")
    return claims
