"""
Tests for the GitHub connect-account flow.

The token exchange and the GitHub API call are mocked, so nothing here talks to
github.com. What is exercised for real: state signing and verification, the
authorize URL, encryption of the stored token, and the route behaviour.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from jose import jwt
from sqlalchemy import select

from app.config import settings
from app.github import client as github_client
from app.github import oauth
from app.github.crypto import TokenEncryptionError, decrypt_token, encrypt_token
from app.models.github import GitHubConnection

FAKE_TOKEN = "gho_averysecrettoken"
FAKE_GITHUB_USER = {"login": "octocat", "id": 583231}


@pytest.fixture
def github_configured(monkeypatch):
    """Pretend an OAuth App is configured, without needing real credentials."""
    monkeypatch.setattr(settings, "github_client_id", "test-client-id")
    monkeypatch.setattr(settings, "github_client_secret", "test-client-secret")
    monkeypatch.setattr(
        settings, "github_callback_url", "http://localhost:8000/github/callback"
    )
    monkeypatch.setattr(settings, "github_oauth_scopes", "repo,admin:repo_hook")


@pytest.fixture
def successful_github(monkeypatch, github_configured):
    """Mock a successful token exchange and /user lookup."""

    async def fake_exchange(code: str):
        assert code == "the-code"
        return FAKE_TOKEN, "repo,admin:repo_hook"

    async def fake_user(access_token: str):
        assert access_token == FAKE_TOKEN
        return FAKE_GITHUB_USER

    monkeypatch.setattr(oauth, "exchange_code_for_token", fake_exchange)
    monkeypatch.setattr(github_client, "get_authenticated_user", fake_user)


async def _auth_headers(client, credentials) -> dict[str, str]:
    res = await client.post("/auth/signup", json=credentials)
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def _auth(client, credentials) -> tuple[dict[str, str], uuid.UUID]:
    """Sign up and return (headers, user_id).

    Assertions are scoped to this user: the tests share a real database that
    may already hold unrelated rows, so a global `select(...)` would be wrong.
    """
    res = await client.post("/auth/signup", json=credentials)
    return (
        {"Authorization": f"Bearer {res.json()['access_token']}"},
        uuid.UUID(res.json()["user"]["id"]),
    )


def _connections_for(user_id: uuid.UUID):
    return select(GitHubConnection).where(GitHubConnection.user_id == user_id)


async def _count_connections(db) -> int:
    return len((await db.execute(select(GitHubConnection))).scalars().all())


# --- Token encryption -------------------------------------------------------

def test_encrypted_token_round_trips():
    encrypted = encrypt_token(FAKE_TOKEN)
    assert decrypt_token(encrypted) == FAKE_TOKEN


def test_ciphertext_does_not_contain_the_plaintext():
    assert FAKE_TOKEN not in encrypt_token(FAKE_TOKEN)


def test_encrypting_twice_gives_different_ciphertext():
    """Fernet includes a random IV, so identical tokens do not look identical."""
    assert encrypt_token(FAKE_TOKEN) != encrypt_token(FAKE_TOKEN)


def test_decrypting_with_a_different_key_fails_loudly(monkeypatch):
    from cryptography.fernet import Fernet

    from app.github import crypto

    encrypted = encrypt_token(FAKE_TOKEN)
    crypto._fernet.cache_clear()
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    try:
        with pytest.raises(TokenEncryptionError):
            decrypt_token(encrypted)
    finally:
        crypto._fernet.cache_clear()


def test_empty_token_is_refused():
    with pytest.raises(TokenEncryptionError):
        encrypt_token("")


# --- OAuth state ------------------------------------------------------------

def test_state_round_trips_the_user_id():
    user_id = uuid.uuid4()
    assert oauth.verify_state(oauth.create_state(user_id)) == user_id


def test_each_state_is_unique():
    """A fresh random nonce every time, so states cannot collide or be reused."""
    user_id = uuid.uuid4()
    assert oauth.create_state(user_id) != oauth.create_state(user_id)


def test_missing_state_is_rejected():
    with pytest.raises(oauth.GitHubOAuthError):
        oauth.verify_state("")


def test_tampered_state_is_rejected():
    state = oauth.create_state(uuid.uuid4())
    with pytest.raises(oauth.GitHubOAuthError):
        oauth.verify_state(state[:-2] + "xy")


def test_state_signed_with_another_secret_is_rejected():
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "github_oauth_state"},
        "some-other-secret",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(oauth.GitHubOAuthError):
        oauth.verify_state(forged)


def test_expired_state_is_rejected():
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "github_oauth_state",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(oauth.GitHubOAuthError):
        oauth.verify_state(expired)


def test_an_app_access_token_is_not_accepted_as_state():
    """Tokens are single-purpose: a login JWT must not work as OAuth state."""
    from app.auth.security import create_access_token

    with pytest.raises(oauth.GitHubOAuthError):
        oauth.verify_state(create_access_token(uuid.uuid4()))


# --- Authorize URL ----------------------------------------------------------

def test_authorize_url_has_the_required_parameters(github_configured):
    state = oauth.create_state(uuid.uuid4())
    parsed = urlparse(oauth.build_authorize_url(state))
    query = parse_qs(parsed.query)

    assert parsed.netloc == "github.com"
    assert parsed.path == "/login/oauth/authorize"
    assert query["client_id"] == ["test-client-id"]
    assert query["scope"] == ["repo,admin:repo_hook"]
    assert query["state"] == [state]
    assert query["redirect_uri"] == ["http://localhost:8000/github/callback"]


def test_authorize_url_never_contains_the_client_secret(github_configured):
    assert "test-client-secret" not in oauth.build_authorize_url(
        oauth.create_state(uuid.uuid4())
    )


def test_unconfigured_server_reports_it(monkeypatch):
    monkeypatch.setattr(settings, "github_client_id", "")
    monkeypatch.setattr(settings, "github_client_secret", "")
    with pytest.raises(oauth.GitHubNotConfiguredError):
        oauth.build_authorize_url("state")


# --- Token exchange (mocked transport) --------------------------------------

@pytest.mark.asyncio
async def test_exchange_sends_the_secret_and_returns_the_token(
    monkeypatch, github_configured
):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        return httpx.Response(
            200, json={"access_token": FAKE_TOKEN, "scope": "repo,admin:repo_hook"}
        )

    _patch_httpx(monkeypatch, handler)

    token, scopes = await oauth.exchange_code_for_token("the-code")
    assert token == FAKE_TOKEN
    assert scopes == "repo,admin:repo_hook"
    # The secret goes in the POST body, to GitHub, over TLS — never in a URL.
    assert seen["url"] == oauth.GITHUB_TOKEN_URL
    assert "client_secret=test-client-secret" in seen["body"]
    assert "code=the-code" in seen["body"]


@pytest.mark.asyncio
async def test_exchange_surfaces_a_github_error(monkeypatch, github_configured):
    _patch_httpx(
        monkeypatch,
        lambda request: httpx.Response(200, json={"error": "bad_verification_code"}),
    )
    with pytest.raises(oauth.GitHubOAuthError, match="bad_verification_code"):
        await oauth.exchange_code_for_token("stale-code")


@pytest.mark.asyncio
async def test_exchange_without_a_code_does_not_call_github(github_configured):
    with pytest.raises(oauth.GitHubOAuthError):
        await oauth.exchange_code_for_token("")


def _patch_httpx(monkeypatch, handler) -> None:
    """Route every httpx.AsyncClient in this test through a mock transport."""
    real_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


# --- Routes -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_requires_login(client):
    assert (await client.get("/github/connect")).status_code == 401


@pytest.mark.asyncio
async def test_connect_returns_an_authorize_url(client, user_credentials, github_configured):
    headers = await _auth_headers(client, user_credentials)
    res = await client.get("/github/connect", headers=headers)
    assert res.status_code == 200
    assert res.json()["authorize_url"].startswith(
        "https://github.com/login/oauth/authorize?"
    )


@pytest.mark.asyncio
async def test_status_is_disconnected_before_connecting(client, user_credentials):
    headers = await _auth_headers(client, user_credentials)
    res = await client.get("/github/status", headers=headers)
    assert res.status_code == 200
    assert res.json() == {
        "connected": False,
        "github_username": None,
        "github_user_id": None,
        "scopes": None,
        "connected_at": None,
    }


@pytest.mark.asyncio
async def test_callback_stores_an_encrypted_connection(
    client, db_session, user_credentials, successful_github
):
    headers, user_id = await _auth(client, user_credentials)
    state = parse_qs(
        urlparse((await client.get("/github/connect", headers=headers)).json()["authorize_url"]).query
    )["state"][0]

    res = await client.get(
        "/github/callback", params={"code": "the-code", "state": state}
    )
    assert res.status_code == 302
    assert "github=connected" in res.headers["location"]

    connection = (await db_session.execute(_connections_for(user_id))).scalar_one()
    assert connection.github_username == "octocat"
    assert connection.github_user_id == 583231
    assert connection.scopes == "repo,admin:repo_hook"
    # The whole point: what is in the database is not the token.
    assert connection.access_token_enc != FAKE_TOKEN
    assert FAKE_TOKEN not in connection.access_token_enc
    assert decrypt_token(connection.access_token_enc) == FAKE_TOKEN


@pytest.mark.asyncio
async def test_status_reports_the_connection_without_the_token(
    client, user_credentials, successful_github
):
    headers = await _auth_headers(client, user_credentials)
    state = parse_qs(
        urlparse((await client.get("/github/connect", headers=headers)).json()["authorize_url"]).query
    )["state"][0]
    await client.get("/github/callback", params={"code": "the-code", "state": state})

    res = await client.get("/github/status", headers=headers)
    body = res.json()
    assert body["connected"] is True
    assert body["github_username"] == "octocat"
    assert FAKE_TOKEN not in res.text
    assert "access_token" not in res.text


@pytest.mark.asyncio
async def test_callback_with_a_forged_state_stores_nothing(
    client, db_session, successful_github
):
    before = await _count_connections(db_session)
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "github_oauth_state"},
        "not-the-app-secret",
        algorithm=settings.jwt_algorithm,
    )
    res = await client.get("/github/callback", params={"code": "the-code", "state": forged})
    assert res.status_code == 302
    assert "github=error" in res.headers["location"]
    assert await _count_connections(db_session) == before


@pytest.mark.asyncio
async def test_callback_without_a_state_stores_nothing(client, db_session, successful_github):
    before = await _count_connections(db_session)
    res = await client.get("/github/callback", params={"code": "the-code"})
    assert "github=error" in res.headers["location"]
    assert await _count_connections(db_session) == before


@pytest.mark.asyncio
async def test_callback_when_the_user_cancels_on_github(client, db_session):
    before = await _count_connections(db_session)
    res = await client.get(
        "/github/callback",
        params={"error": "access_denied", "error_description": "The user denied access"},
    )
    assert res.status_code == 302
    assert "github=error" in res.headers["location"]
    assert await _count_connections(db_session) == before


@pytest.mark.asyncio
async def test_reconnecting_replaces_the_token_and_keeps_one_row(
    client, db_session, user_credentials, successful_github
):
    headers, user_id = await _auth(client, user_credentials)

    async def connect_once():
        url = (await client.get("/github/connect", headers=headers)).json()["authorize_url"]
        state = parse_qs(urlparse(url).query)["state"][0]
        await client.get("/github/callback", params={"code": "the-code", "state": state})

    await connect_once()
    first = (
        await db_session.execute(_connections_for(user_id))
    ).scalar_one().access_token_enc
    await connect_once()

    rows = (await db_session.execute(_connections_for(user_id))).scalars().all()
    assert len(rows) == 1  # one connection per user
    assert rows[0].access_token_enc != first  # re-encrypted with a fresh IV
    assert decrypt_token(rows[0].access_token_enc) == FAKE_TOKEN


@pytest.mark.asyncio
async def test_disconnect_removes_the_stored_token(
    client, db_session, user_credentials, successful_github
):
    headers, user_id = await _auth(client, user_credentials)
    url = (await client.get("/github/connect", headers=headers)).json()["authorize_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    await client.get("/github/callback", params={"code": "the-code", "state": state})

    assert (await client.delete("/github/disconnect", headers=headers)).status_code == 204
    assert (await db_session.execute(_connections_for(user_id))).first() is None
    assert (await client.get("/github/status", headers=headers)).json()["connected"] is False


@pytest.mark.asyncio
async def test_one_users_state_cannot_connect_to_another_users_account(
    client, db_session, user_credentials, admin_credentials, successful_github
):
    """The connection is created for whoever the state was issued to."""
    alice_headers, alice_id = await _auth(client, user_credentials)
    await _auth_headers(client, admin_credentials)  # a second, unrelated account

    url = (await client.get("/github/connect", headers=alice_headers)).json()["authorize_url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    await client.get("/github/callback", params={"code": "the-code", "state": state})

    connection = (await db_session.execute(_connections_for(alice_id))).scalar_one()
    assert connection.user_id == alice_id


def test_placeholder_credentials_count_as_unconfigured(monkeypatch):
    """The .env.example placeholders must not be mistaken for real credentials."""
    monkeypatch.setattr(settings, "github_client_id", "your-client-id")
    monkeypatch.setattr(settings, "github_client_secret", "your-client-secret")
    with pytest.raises(oauth.GitHubNotConfiguredError):
        oauth.build_authorize_url("state")
