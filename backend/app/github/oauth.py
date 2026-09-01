"""
GitHub OAuth: starting the flow and exchanging the code for a token.

This is a *connect account* flow layered on top of an existing DeployForge
login — not a way to log in. The user is already authenticated when they start
it, and the resulting token is DeployForge's permission to reach their GitHub.

The client secret and the token exchange never leave the backend.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import JWTError, jwt

from app.config import settings
from app.core.errors import AppError

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"

# The OAuth round trip is a browser redirect or two — minutes at most.
STATE_TTL_MINUTES = 10
_STATE_TOKEN_TYPE = "github_oauth_state"


class GitHubOAuthError(AppError):
    code = "github_oauth_error"


class GitHubNotConfiguredError(AppError):
    code = "github_not_configured"
    status_code = 503


# The placeholder values shipped in .env.example. Treating them as "unset"
# turns a confusing failure on github.com into a clear message from us.
_PLACEHOLDERS = frozenset({"your-client-id", "your-client-secret", "change-me"})


def _is_unset(value: str) -> bool:
    return not value.strip() or value.strip().lower() in _PLACEHOLDERS


def ensure_configured() -> None:
    """Fail with a clear message when the OAuth App credentials are absent."""
    missing = [
        name
        for name, value in (
            ("GITHUB_CLIENT_ID", settings.github_client_id),
            ("GITHUB_CLIENT_SECRET", settings.github_client_secret),
        )
        if _is_unset(value)
    ]
    if missing:
        raise GitHubNotConfiguredError(
            "GitHub OAuth is not configured on the server: "
            f"{', '.join(missing)} not set. Create a GitHub OAuth App and put "
            "the credentials in backend/.env — see .env.example."
        )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def create_state(user_id: uuid.UUID | str) -> str:
    """
    Build the `state` value for an authorization request.

    It is a short-lived signed token carrying a random nonce and the id of the
    user who started the flow. The nonce and signature are the CSRF defence:
    an attacker cannot forge a state, and a state cannot be replayed past its
    expiry. Carrying the user id solves the other half of the problem — GitHub
    redirects the browser back to us with no Authorization header, so the state
    is the only thing that says whose connection this is.
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": _STATE_TOKEN_TYPE,
        "nonce": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(minutes=STATE_TTL_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_state(state: str) -> uuid.UUID:
    """
    Validate a returned `state` and recover the user id it was issued for.

    Raises GitHubOAuthError if it is missing, tampered with, expired, or is
    some other kind of token (an app access token, say).
    """
    if not state:
        raise GitHubOAuthError("Missing OAuth state.")
    try:
        claims = jwt.decode(
            state, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise GitHubOAuthError("Invalid or expired OAuth state.") from exc

    if claims.get("type") != _STATE_TOKEN_TYPE:
        raise GitHubOAuthError("Invalid OAuth state.")
    try:
        return uuid.UUID(claims["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise GitHubOAuthError("Invalid OAuth state.") from exc


# ---------------------------------------------------------------------------
# Authorization URL
# ---------------------------------------------------------------------------

def build_authorize_url(state: str) -> str:
    """The GitHub URL to send the user's browser to."""
    ensure_configured()
    query = urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.github_callback_url,
            "scope": settings.github_oauth_scopes,
            "state": state,
            # Always show the confirmation page, so a user can switch accounts.
            "allow_signup": "false",
        }
    )
    return f"{GITHUB_AUTHORIZE_URL}?{query}"


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------

async def exchange_code_for_token(code: str) -> tuple[str, str]:
    """
    Trade a temporary `code` for an access token. Server-side only.

    Returns (access_token, granted_scopes). Raises GitHubOAuthError on any
    failure — the message never includes the code or the token.
    """
    ensure_configured()
    if not code:
        raise GitHubOAuthError("GitHub did not return an authorization code.")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                GITHUB_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": settings.github_callback_url,
                },
            )
    except httpx.HTTPError as exc:
        raise GitHubOAuthError(f"Could not reach GitHub: {type(exc).__name__}") from exc

    if response.status_code != 200:
        raise GitHubOAuthError(
            f"GitHub rejected the token exchange (HTTP {response.status_code})."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise GitHubOAuthError("GitHub returned an unreadable token response.") from exc

    if payload.get("error"):
        # e.g. bad_verification_code, incorrect_client_credentials
        raise GitHubOAuthError(
            f"GitHub refused the authorization: {payload.get('error')}."
        )

    access_token = payload.get("access_token")
    if not access_token:
        raise GitHubOAuthError("GitHub did not return an access token.")

    return access_token, payload.get("scope", "") or ""
