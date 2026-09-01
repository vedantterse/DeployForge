"""
Tests for per-target environment variables.

The important properties: values are encrypted at rest, secrets never come back
out, and one user cannot read or write another user's configuration.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.crypto import decrypt_value
from app.models.environment import EnvironmentVariable
from app.models.repository import DetectedType, Repository


async def _signup(client, credentials):
    res = await client.post("/auth/signup", json=credentials)
    return (
        {"Authorization": f"Bearer {res.json()['access_token']}"},
        uuid.UUID(res.json()["user"]["id"]),
    )


async def _target(db, user_id, *, github_repo_id: int = 1296269) -> Repository:
    repository = Repository(
        user_id=user_id,
        github_repo_id=github_repo_id,
        name="hello-world",
        full_name="octocat/hello-world",
        default_branch="main",
        clone_url="https://github.com/octocat/hello-world.git",
        detected_type=DetectedType.FRAMEWORK,
        detected_framework="django",
    )
    db.add(repository)
    await db.commit()
    await db.refresh(repository)
    return repository


async def _save(client, headers, repo_id, variables):
    return await client.put(
        f"/repos/{repo_id}/env", json={"variables": variables}, headers=headers
    )


# --- Saving and reading -----------------------------------------------------

@pytest.mark.asyncio
async def test_a_new_target_has_no_variables(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    res = await client.get(f"/repos/{repo.id}/env", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_saving_and_reading_a_plain_variable(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)

    res = await _save(client, headers, repo.id, [
        {"key": "PORT", "value": "8000", "is_secret": False},
    ])
    assert res.status_code == 200
    saved = res.json()[0]
    assert saved["key"] == "PORT"
    assert saved["value"] == "8000"  # not secret, so it is readable
    assert saved["is_secret"] is False


@pytest.mark.asyncio
async def test_values_are_encrypted_at_rest(client, db_session, user_credentials):
    """Even a non-secret value must not sit in the database as plaintext."""
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    await _save(client, headers, repo.id, [
        {"key": "DATABASE_URL", "value": "postgres://u:p@host/db", "is_secret": False},
    ])

    stored = (
        await db_session.execute(
            select(EnvironmentVariable).where(EnvironmentVariable.repository_id == repo.id)
        )
    ).scalar_one()
    assert "postgres://" not in stored.value_enc
    assert stored.value_enc != "postgres://u:p@host/db"
    assert decrypt_value(stored.value_enc) == "postgres://u:p@host/db"


@pytest.mark.asyncio
async def test_a_secret_value_is_never_returned(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    await _save(client, headers, repo.id, [
        {"key": "STRIPE_KEY", "value": "sk_live_abc123", "is_secret": True},
    ])

    res = await client.get(f"/repos/{repo.id}/env", headers=headers)
    row = res.json()[0]
    assert row["key"] == "STRIPE_KEY"
    assert row["value"] is None
    assert row["is_secret"] is True
    assert row["has_value"] is True  # the UI still knows something is stored
    assert "sk_live_abc123" not in res.text


@pytest.mark.asyncio
async def test_variables_come_back_sorted_by_key(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    await _save(client, headers, repo.id, [
        {"key": "ZEBRA", "value": "1"},
        {"key": "ALPHA", "value": "2"},
    ])
    keys = [v["key"] for v in (await client.get(f"/repos/{repo.id}/env", headers=headers)).json()]
    assert keys == ["ALPHA", "ZEBRA"]


# --- Replace semantics ------------------------------------------------------

@pytest.mark.asyncio
async def test_saving_replaces_the_whole_set(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    await _save(client, headers, repo.id, [
        {"key": "KEEP", "value": "1"},
        {"key": "DROP", "value": "2"},
    ])
    res = await _save(client, headers, repo.id, [{"key": "KEEP", "value": "1"}])
    assert [v["key"] for v in res.json()] == ["KEEP"]


@pytest.mark.asyncio
async def test_a_null_value_keeps_the_stored_secret(client, db_session, user_credentials):
    """
    The form never sees a secret's value, so it sends null on save. That must
    preserve the stored value rather than blank it.
    """
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    await _save(client, headers, repo.id, [
        {"key": "API_KEY", "value": "the-real-secret", "is_secret": True},
    ])

    # Save again with another variable added; API_KEY comes back with no value.
    await _save(client, headers, repo.id, [
        {"key": "API_KEY", "value": None, "is_secret": True},
        {"key": "DEBUG", "value": "false", "is_secret": False},
    ])

    stored = {
        v.key: v
        for v in (
            await db_session.execute(
                select(EnvironmentVariable).where(
                    EnvironmentVariable.repository_id == repo.id
                )
            )
        ).scalars().all()
    }
    assert decrypt_value(stored["API_KEY"].value_enc) == "the-real-secret"
    assert decrypt_value(stored["DEBUG"].value_enc) == "false"


@pytest.mark.asyncio
async def test_a_null_value_for_a_new_key_is_rejected(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    res = await _save(client, headers, repo.id, [{"key": "NEW_KEY", "value": None}])
    assert res.status_code == 400
    assert "NEW_KEY" in res.text


@pytest.mark.asyncio
async def test_marking_an_existing_variable_secret_hides_it(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    await _save(client, headers, repo.id, [{"key": "TOKEN", "value": "abc", "is_secret": False}])
    await _save(client, headers, repo.id, [{"key": "TOKEN", "value": None, "is_secret": True}])

    row = (await client.get(f"/repos/{repo.id}/env", headers=headers)).json()[0]
    assert row["is_secret"] is True
    assert row["value"] is None


@pytest.mark.asyncio
async def test_saving_an_empty_set_clears_everything(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    await _save(client, headers, repo.id, [{"key": "A", "value": "1"}])
    res = await _save(client, headers, repo.id, [])
    assert res.json() == []


# --- Validation -------------------------------------------------------------

@pytest.mark.parametrize("bad_key", ["1STARTS_WITH_DIGIT", "HAS SPACE", "has-dash", "", "A=B"])
@pytest.mark.asyncio
async def test_invalid_keys_are_rejected(client, db_session, user_credentials, bad_key):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    res = await _save(client, headers, repo.id, [{"key": bad_key, "value": "x"}])
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_keys_are_rejected(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    res = await _save(client, headers, repo.id, [
        {"key": "SAME", "value": "1"},
        {"key": "SAME", "value": "2"},
    ])
    assert res.status_code == 422


# --- Deleting ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_deleting_one_variable(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    await _save(client, headers, repo.id, [
        {"key": "A", "value": "1"},
        {"key": "B", "value": "2"},
    ])
    assert (await client.delete(f"/repos/{repo.id}/env/A", headers=headers)).status_code == 204
    keys = [v["key"] for v in (await client.get(f"/repos/{repo.id}/env", headers=headers)).json()]
    assert keys == ["B"]


@pytest.mark.asyncio
async def test_deleting_a_missing_variable_is_404(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    assert (await client.delete(f"/repos/{repo.id}/env/NOPE", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_deleting_the_target_removes_its_variables(client, db_session, user_credentials):
    """The FK cascades — no orphaned configuration left behind."""
    headers, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    await _save(client, headers, repo.id, [{"key": "A", "value": "1"}])

    await db_session.delete(await db_session.get(Repository, repo.id))
    await db_session.commit()

    remaining = (
        await db_session.execute(
            select(EnvironmentVariable).where(EnvironmentVariable.repository_id == repo.id)
        )
    ).first()
    assert remaining is None


# --- Access control ---------------------------------------------------------

@pytest.mark.asyncio
async def test_env_endpoints_require_login(client, db_session, user_credentials):
    _, user_id = await _signup(client, user_credentials)
    repo = await _target(db_session, user_id)
    assert (await client.get(f"/repos/{repo.id}/env")).status_code == 401
    assert (await client.put(f"/repos/{repo.id}/env", json={"variables": []})).status_code == 401


@pytest.mark.asyncio
async def test_another_user_cannot_read_or_write_your_variables(
    client, db_session, user_credentials, admin_credentials
):
    _, owner_id = await _signup(client, user_credentials)
    repo = await _target(db_session, owner_id)

    other_headers, _ = await _signup(client, admin_credentials)
    assert (await client.get(f"/repos/{repo.id}/env", headers=other_headers)).status_code == 404
    assert (await _save(client, other_headers, repo.id, [{"key": "X", "value": "1"}])).status_code == 404
