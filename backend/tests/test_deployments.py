"""
Tests for the deployment views: a user's own list, and the admin overview.

Rows are created directly rather than through the analyze flow — this is about
who can read what, and what each response contains.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.deployment import BuildMethod, Deployment, DeploymentStatus
from app.models.repository import DetectedType, Repository
from app.models.user import UserRole


async def _signup(client, credentials):
    res = await client.post("/auth/signup", json=credentials)
    return (
        {"Authorization": f"Bearer {res.json()['access_token']}"},
        uuid.UUID(res.json()["user"]["id"]),
    )


async def _make_deployment(
    db,
    user_id: uuid.UUID,
    *,
    full_name: str = "octocat/hello-world",
    deploy_path: str | None = None,
    github_repo_id: int = 1296269,
    framework: str = "django",
    status: DeploymentStatus = DeploymentStatus.ANALYZED,
) -> Deployment:
    repository = Repository(
        user_id=user_id,
        github_repo_id=github_repo_id,
        name=full_name.split("/")[-1],
        full_name=full_name,
        default_branch="main",
        clone_url=f"https://github.com/{full_name}.git",
        deploy_path=deploy_path,
        detected_type=DetectedType.FRAMEWORK,
        detected_framework=framework,
        detection_meta={"type": "framework", "framework": framework},
    )
    db.add(repository)
    await db.flush()
    deployment = Deployment(
        repository_id=repository.id,
        user_id=user_id,
        commit_sha="c" * 40,
        build_method=BuildMethod.BUILDPACK,
        status=status,
    )
    db.add(deployment)
    await db.commit()
    return deployment


# --- A user's own deployments ------------------------------------------------

@pytest.mark.asyncio
async def test_listing_deployments_requires_login(client):
    assert (await client.get("/deployments")).status_code == 401


@pytest.mark.asyncio
async def test_a_new_user_has_no_deployments(client, user_credentials):
    headers, _ = await _signup(client, user_credentials)
    res = await client.get("/deployments", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_deployment_list_includes_the_target_and_status(
    client, db_session, user_credentials
):
    headers, user_id = await _signup(client, user_credentials)
    await _make_deployment(db_session, user_id, deploy_path="backend")

    res = await client.get("/deployments", headers=headers)
    assert res.status_code == 200
    row = res.json()[0]
    assert row["full_name"] == "octocat/hello-world"
    assert row["deploy_path"] == "backend"
    assert row["target_label"] == "octocat/hello-world (backend/)"
    assert row["status"] == "analyzed"
    assert row["build_method"] == "buildpack"
    assert row["detected_framework"] == "django"
    assert row["created_at"]  # the date/time shown in the UI


@pytest.mark.asyncio
async def test_a_user_never_sees_another_users_deployments(
    client, db_session, user_credentials, admin_credentials
):
    _, other_id = await _signup(client, admin_credentials)
    await _make_deployment(db_session, other_id, full_name="someone/else")

    headers, _ = await _signup(client, user_credentials)
    res = await client.get("/deployments", headers=headers)
    assert res.json() == []


@pytest.mark.asyncio
async def test_own_deployment_list_does_not_leak_owner_fields(
    client, db_session, user_credentials
):
    """user_email is an admin-view field; it stays null on your own list."""
    headers, user_id = await _signup(client, user_credentials)
    await _make_deployment(db_session, user_id)
    row = (await client.get("/deployments", headers=headers)).json()[0]
    assert row["user_email"] is None


@pytest.mark.asyncio
async def test_deployments_are_newest_first(client, db_session, user_credentials):
    from datetime import datetime, timedelta, timezone

    headers, user_id = await _signup(client, user_credentials)
    older = await _make_deployment(db_session, user_id, github_repo_id=1, full_name="a/one")
    newer = await _make_deployment(db_session, user_id, github_repo_id=2, full_name="a/two")

    # PostgreSQL's now() is fixed for a transaction, and this whole test runs in
    # one — so the timestamps are set explicitly to make the order meaningful.
    base = datetime.now(timezone.utc)
    older.created_at = base - timedelta(hours=1)
    newer.created_at = base
    await db_session.commit()

    rows = (await client.get("/deployments", headers=headers)).json()
    assert [r["full_name"] for r in rows] == ["a/two", "a/one"]


# --- Admin views -------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_deployment_views_reject_a_normal_user(client, user_credentials):
    headers, _ = await _signup(client, user_credentials)
    assert (await client.get("/admin/deployments", headers=headers)).status_code == 403
    assert (await client.get("/admin/overview", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_admin_deployment_views_reject_anonymous(client):
    assert (await client.get("/admin/deployments")).status_code == 401
    assert (await client.get("/admin/overview")).status_code == 401


@pytest.mark.asyncio
async def test_admin_sees_every_deployment_with_its_owner(
    client, db_session, user_credentials, admin_credentials
):
    from app.auth.service import signup

    _, user_id = await _signup(client, user_credentials)
    await _make_deployment(db_session, user_id, full_name="person/app")

    await signup(
        db_session,
        admin_credentials["email"],
        admin_credentials["password"],
        role=UserRole.ADMIN,
    )
    admin_headers = {
        "Authorization": "Bearer "
        + (await client.post("/auth/login", json=admin_credentials)).json()["access_token"]
    }

    rows = (await client.get("/admin/deployments", headers=admin_headers)).json()
    mine = [r for r in rows if r["full_name"] == "person/app"]
    assert len(mine) == 1
    assert mine[0]["user_email"] == user_credentials["email"]
    assert mine[0]["user_id"] == str(user_id)


@pytest.mark.asyncio
async def test_admin_overview_groups_deployments_under_each_user(
    client, db_session, user_credentials, admin_credentials
):
    from app.auth.service import signup

    _, user_id = await _signup(client, user_credentials)
    await _make_deployment(db_session, user_id, github_repo_id=11, full_name="person/one")
    await _make_deployment(db_session, user_id, github_repo_id=22, full_name="person/two")

    await signup(
        db_session,
        admin_credentials["email"],
        admin_credentials["password"],
        role=UserRole.ADMIN,
    )
    admin_headers = {
        "Authorization": "Bearer "
        + (await client.post("/auth/login", json=admin_credentials)).json()["access_token"]
    }

    overview = (await client.get("/admin/overview", headers=admin_headers)).json()
    person = next(u for u in overview if u["email"] == user_credentials["email"])
    assert person["deployment_count"] == 2
    assert person["repository_count"] == 2
    assert {d["full_name"] for d in person["deployments"]} == {"person/one", "person/two"}

    admin_entry = next(u for u in overview if u["email"] == admin_credentials["email"])
    assert admin_entry["role"] == "admin"
    assert admin_entry["deployments"] == []


@pytest.mark.asyncio
async def test_admin_overview_reports_the_github_handle(
    client, db_session, user_credentials, admin_credentials
):
    from app.auth.service import signup
    from app.github.crypto import encrypt_token
    from app.models.github import GitHubConnection

    _, user_id = await _signup(client, user_credentials)
    db_session.add(
        GitHubConnection(
            user_id=user_id,
            github_username="octocat",
            github_user_id=583231,
            access_token_enc=encrypt_token("gho_token"),
            scopes="repo",
        )
    )
    await db_session.commit()

    await signup(
        db_session,
        admin_credentials["email"],
        admin_credentials["password"],
        role=UserRole.ADMIN,
    )
    admin_headers = {
        "Authorization": "Bearer "
        + (await client.post("/auth/login", json=admin_credentials)).json()["access_token"]
    }

    overview = (await client.get("/admin/overview", headers=admin_headers)).json()
    person = next(u for u in overview if u["email"] == user_credentials["email"])
    assert person["github_username"] == "octocat"
    # No token, encrypted or otherwise, in an admin response.
    body = (await client.get("/admin/overview", headers=admin_headers)).text
    assert "gho_token" not in body and "access_token_enc" not in body
