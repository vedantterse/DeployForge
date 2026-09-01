"""
Tests for app authentication: password hashing, JWTs, the signup/login/me
endpoints, and the admin role check.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.auth.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.auth.service import signup
from app.config import settings
from app.models.user import UserRole


# --- Password hashing (no DB) ----------------------------------------------

def test_hash_is_not_the_plaintext():
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"
    assert hashed.startswith("$2")


def test_verify_accepts_correct_and_rejects_wrong_password():
    hashed = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_same_password_hashes_differently_each_time():
    """Distinct salts — two users with the same password get different hashes."""
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_does_not_raise_on_a_malformed_hash():
    assert verify_password("anything", "not-a-bcrypt-hash") is False


# --- JWTs (no DB) -----------------------------------------------------------

def test_token_round_trips_the_user_id():
    user_id = uuid.uuid4()
    claims = decode_token(create_access_token(user_id))
    assert claims is not None
    assert claims["sub"] == str(user_id)


def test_token_signed_with_another_secret_is_rejected():
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access"},
        "a-different-secret",
        algorithm=settings.jwt_algorithm,
    )
    assert decode_token(forged) is None


def test_expired_token_is_rejected():
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    expired = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "exp": past},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert decode_token(expired) is None


def test_garbage_token_is_rejected():
    assert decode_token("not.a.jwt") is None


def test_token_does_not_carry_the_role():
    """Authorization reads the role from the DB, so it must not be in the token."""
    claims = decode_token(create_access_token(uuid.uuid4()))
    assert claims is not None and "role" not in claims


# --- Signup -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_signup_creates_a_user_and_returns_a_token(client, user_credentials):
    res = await client.post("/auth/signup", json=user_credentials)
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == user_credentials["email"]
    assert body["user"]["role"] == "user"
    assert body["user"]["is_active"] is True


@pytest.mark.asyncio
async def test_signup_never_returns_the_password_hash(client, user_credentials):
    res = await client.post("/auth/signup", json=user_credentials)
    assert "hashed_password" not in res.text
    assert user_credentials["password"] not in res.text


@pytest.mark.asyncio
async def test_signup_stores_a_hash_not_the_plaintext(client, db_session, user_credentials):
    await client.post("/auth/signup", json=user_credentials)
    from app.auth.service import get_user_by_email

    user = await get_user_by_email(db_session, user_credentials["email"])
    assert user is not None
    assert user.hashed_password != user_credentials["password"]
    assert verify_password(user_credentials["password"], user.hashed_password)


@pytest.mark.asyncio
async def test_signup_rejects_a_duplicate_email(client, user_credentials):
    await client.post("/auth/signup", json=user_credentials)
    res = await client.post("/auth/signup", json=user_credentials)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_signup_email_is_case_insensitive(client, user_credentials):
    await client.post("/auth/signup", json=user_credentials)
    res = await client.post(
        "/auth/signup",
        json={**user_credentials, "email": user_credentials["email"].upper()},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_signup_rejects_a_short_password(client):
    res = await client.post(
        "/auth/signup", json={"email": "a@example.com", "password": "short"}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_signup_rejects_a_password_past_bcrypts_limit(client):
    """Over 72 bytes bcrypt silently truncates, so we refuse it outright."""
    res = await client.post(
        "/auth/signup", json={"email": "a@example.com", "password": "a" * 80}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_signup_rejects_an_invalid_email(client):
    res = await client.post(
        "/auth/signup", json={"email": "not-an-email", "password": "long-enough-pw"}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_signup_cannot_grant_itself_the_admin_role(client, user_credentials):
    """An extra `role` field in the request body must be ignored."""
    res = await client.post(
        "/auth/signup", json={**user_credentials, "role": "admin"}
    )
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "user"


# --- Login ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_succeeds_with_correct_credentials(client, user_credentials):
    await client.post("/auth/signup", json=user_credentials)
    res = await client.post("/auth/login", json=user_credentials)
    assert res.status_code == 200
    assert res.json()["access_token"]


@pytest.mark.asyncio
async def test_login_fails_with_the_wrong_password(client, user_credentials):
    await client.post("/auth/signup", json=user_credentials)
    res = await client.post(
        "/auth/login", json={**user_credentials, "password": "not-the-password"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_with_an_unknown_email_looks_identical_to_a_wrong_password(
    client, user_credentials
):
    """Same status and message, so the endpoint cannot enumerate accounts."""
    await client.post("/auth/signup", json=user_credentials)
    wrong_pw = await client.post(
        "/auth/login", json={**user_credentials, "password": "not-the-password"}
    )
    unknown = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever12"}
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


@pytest.mark.asyncio
async def test_disabled_account_cannot_log_in(client, db_session, user_credentials):
    await client.post("/auth/signup", json=user_credentials)
    from app.auth.service import get_user_by_email

    user = await get_user_by_email(db_session, user_credentials["email"])
    user.is_active = False
    await db_session.commit()

    res = await client.post("/auth/login", json=user_credentials)
    assert res.status_code == 401


# --- /auth/me ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_me_returns_the_authenticated_user(client, user_credentials):
    token = (await client.post("/auth/signup", json=user_credentials)).json()["access_token"]
    res = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == user_credentials["email"]


@pytest.mark.asyncio
async def test_me_requires_a_token(client):
    assert (await client.get("/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_a_forged_token(client):
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access"},
        "a-different-secret",
        algorithm=settings.jwt_algorithm,
    )
    res = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_a_valid_token_for_a_deleted_user(client, db_session):
    """Correctly signed, but the account no longer exists."""
    token = create_access_token(uuid.uuid4())
    res = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


# --- Roles: admin vs user ---------------------------------------------------

@pytest.mark.asyncio
async def test_admin_routes_reject_an_anonymous_caller(client):
    assert (await client.get("/admin/users")).status_code == 401


@pytest.mark.asyncio
async def test_admin_routes_reject_a_normal_user_with_403(client, user_credentials):
    token = (await client.post("/auth/signup", json=user_credentials)).json()["access_token"]
    res = await client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_reach_admin_routes(client, db_session, admin_credentials):
    admin = await signup(
        db_session,
        admin_credentials["email"],
        admin_credentials["password"],
        role=UserRole.ADMIN,
    )
    assert admin.role == UserRole.ADMIN

    token = (await client.post("/auth/login", json=admin_credentials)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    users = await client.get("/admin/users", headers=headers)
    assert users.status_code == 200
    assert any(u["email"] == admin_credentials["email"] for u in users.json())

    stats = await client.get("/admin/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["admins"] >= 1


@pytest.mark.asyncio
async def test_demoting_an_admin_takes_effect_immediately_on_an_existing_token(
    client, db_session, admin_credentials
):
    """The role lives in the DB, not the token, so an old token loses access."""
    admin = await signup(
        db_session,
        admin_credentials["email"],
        admin_credentials["password"],
        role=UserRole.ADMIN,
    )
    token = (await client.post("/auth/login", json=admin_credentials)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/admin/users", headers=headers)).status_code == 200

    admin.role = UserRole.USER
    await db_session.commit()

    assert (await client.get("/admin/users", headers=headers)).status_code == 403
