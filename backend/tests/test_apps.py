"""
Tests for the app view — what a student sees when they look at their work.

The distinction under test is between an *app* (a connected repository target)
and a *deployment* (one attempt to build and run it). Redeploying makes a
second deployment, not a second app, and the list has to say so.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.deployment import BuildMethod, Deployment, DeploymentStatus
from app.models.repository import DetectedType, Repository


async def _signup(client, credentials):
    res = await client.post("/auth/signup", json=credentials)
    return (
        {"Authorization": f"Bearer {res.json()['access_token']}"},
        uuid.UUID(res.json()["user"]["id"]),
    )


async def _make_app(
    db,
    user_id: uuid.UUID,
    *,
    full_name: str = "octocat/hello-world",
    github_repo_id: int = 1296269,
    deploy_path: str | None = None,
) -> Repository:
    repository = Repository(
        user_id=user_id,
        github_repo_id=github_repo_id,
        name=full_name.split("/")[-1],
        full_name=full_name,
        default_branch="main",
        clone_url=f"https://github.com/{full_name}.git",
        deploy_path=deploy_path,
        detected_type=DetectedType.FRAMEWORK,
        detected_framework="django",
    )
    db.add(repository)
    await db.flush()
    return repository


async def _add_deployment(
    db,
    repository: Repository,
    *,
    status: DeploymentStatus,
    minutes_ago: int = 0,
) -> Deployment:
    deployment = Deployment(
        repository_id=repository.id,
        user_id=repository.user_id,
        commit_sha="c" * 40,
        build_method=BuildMethod.BUILDPACK,
        status=status,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    db.add(deployment)
    await db.commit()
    return deployment


# --- The list is a list of apps ---------------------------------------------

@pytest.mark.asyncio
async def test_rebuilding_does_not_add_a_second_app(
    client, db_session, user_credentials
):
    """
    The complaint this view exists to answer.

    Three builds of one repository are three deployments of one app, and the
    student has one app.
    """
    headers, user_id = await _signup(client, user_credentials)
    repository = await _make_app(db_session, user_id)
    for i in range(3):
        await _add_deployment(
            db_session, repository, status=DeploymentStatus.FAILED, minutes_ago=i
        )

    res = await client.get("/apps", headers=headers)
    assert res.status_code == 200
    apps = res.json()
    assert len(apps) == 1
    assert apps[0]["deployment_count"] == 3


@pytest.mark.asyncio
async def test_a_running_deployment_is_the_app_s_current_state(
    client, db_session, user_credentials
):
    """
    A failed redeploy does not take a working app down.

    The newest attempt failed; the app is still serving from the one before it,
    and reporting the app as failed would be false.
    """
    headers, user_id = await _signup(client, user_credentials)
    repository = await _make_app(db_session, user_id)
    await _add_deployment(
        db_session, repository, status=DeploymentStatus.RUNNING, minutes_ago=10
    )
    await _add_deployment(
        db_session, repository, status=DeploymentStatus.FAILED, minutes_ago=0
    )

    apps = (await client.get("/apps", headers=headers)).json()
    assert apps[0]["current"]["status"] == "running"


@pytest.mark.asyncio
async def test_without_anything_running_the_newest_attempt_is_current(
    client, db_session, user_credentials
):
    """A failure the student needs to see is not hidden behind an older one."""
    headers, user_id = await _signup(client, user_credentials)
    repository = await _make_app(db_session, user_id)
    await _add_deployment(
        db_session, repository, status=DeploymentStatus.STOPPED, minutes_ago=10
    )
    newest = await _add_deployment(
        db_session, repository, status=DeploymentStatus.FAILED, minutes_ago=0
    )

    apps = (await client.get("/apps", headers=headers)).json()
    assert apps[0]["current"]["id"] == str(newest.id)


@pytest.mark.asyncio
async def test_a_connected_but_never_built_app_reports_no_deployments(
    client, db_session, user_credentials
):
    """
    Selecting a target writes an `analyzed` row. That is bookkeeping, not
    something the student did, so it is not counted or listed.
    """
    headers, user_id = await _signup(client, user_credentials)
    repository = await _make_app(db_session, user_id)
    await _add_deployment(db_session, repository, status=DeploymentStatus.ANALYZED)

    apps = (await client.get("/apps", headers=headers)).json()
    assert apps[0]["deployment_count"] == 0
    assert apps[0]["last_deployed_at"] is None


@pytest.mark.asyncio
async def test_one_repository_deployed_twice_is_two_apps(
    client, db_session, user_credentials
):
    """A monorepo's frontend and backend are separate apps, deployed apart."""
    headers, user_id = await _signup(client, user_credentials)
    await _make_app(db_session, user_id, deploy_path="frontend")
    await _make_app(db_session, user_id, deploy_path="backend")
    await db_session.commit()

    apps = (await client.get("/apps", headers=headers)).json()
    assert len(apps) == 2
    assert {a["deploy_path"] for a in apps} == {"frontend", "backend"}


@pytest.mark.asyncio
async def test_apps_are_scoped_to_their_owner(
    client, db_session, user_credentials, admin_credentials
):
    headers, user_id = await _signup(client, user_credentials)
    other_headers, other_id = await _signup(client, admin_credentials)
    await _make_app(db_session, other_id, github_repo_id=999)
    await db_session.commit()

    assert (await client.get("/apps", headers=headers)).json() == []
    assert len((await client.get("/apps", headers=other_headers)).json()) == 1


# --- One app's history -------------------------------------------------------

@pytest.mark.asyncio
async def test_an_app_shows_its_own_deployments_only(
    client, db_session, user_credentials
):
    headers, user_id = await _signup(client, user_credentials)
    mine = await _make_app(db_session, user_id, full_name="octocat/mine")
    other = await _make_app(
        db_session, user_id, full_name="octocat/other", github_repo_id=42
    )
    await _add_deployment(db_session, mine, status=DeploymentStatus.RUNNING)
    await _add_deployment(db_session, mine, status=DeploymentStatus.FAILED)
    await _add_deployment(db_session, other, status=DeploymentStatus.RUNNING)

    detail = (await client.get(f"/apps/{mine.id}", headers=headers)).json()
    assert len(detail["deployments"]) == 2
    assert all(d["repository_id"] == str(mine.id) for d in detail["deployments"])


@pytest.mark.asyncio
async def test_history_is_newest_first(client, db_session, user_credentials):
    headers, user_id = await _signup(client, user_credentials)
    repository = await _make_app(db_session, user_id)
    old = await _add_deployment(
        db_session, repository, status=DeploymentStatus.STOPPED, minutes_ago=30
    )
    new = await _add_deployment(
        db_session, repository, status=DeploymentStatus.RUNNING, minutes_ago=1
    )

    detail = (await client.get(f"/apps/{repository.id}", headers=headers)).json()
    assert [d["id"] for d in detail["deployments"]] == [str(new.id), str(old.id)]


@pytest.mark.asyncio
async def test_another_users_app_is_not_found(
    client, db_session, user_credentials, admin_credentials
):
    """Not 403 — the existence of someone else's app is not the caller's to know."""
    headers, _ = await _signup(client, user_credentials)
    _, other_id = await _signup(client, admin_credentials)
    theirs = await _make_app(db_session, other_id, github_repo_id=999)
    await db_session.commit()

    assert (await client.get(f"/apps/{theirs.id}", headers=headers)).status_code == 404


@pytest.mark.asyncio
async def test_apps_require_a_token(client):
    assert (await client.get("/apps")).status_code == 401


# --- Deleting an app ---------------------------------------------------------

@pytest.mark.asyncio
async def test_deleting_an_app_removes_the_connection_too(
    client, db_session, user_credentials, monkeypatch
):
    """
    Otherwise the repository stays connected but invisible, and reconnecting it
    collides with the row still holding its place.
    """
    from app.runtime import docker

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(docker, "stop_container", noop)
    monkeypatch.setattr(docker, "remove_container", noop)

    headers, user_id = await _signup(client, user_credentials)
    repository = await _make_app(db_session, user_id)
    await _add_deployment(db_session, repository, status=DeploymentStatus.STOPPED)

    res = await client.delete(f"/apps/{repository.id}", headers=headers)
    assert res.status_code == 204
    assert (await client.get("/apps", headers=headers)).json() == []


@pytest.mark.asyncio
async def test_a_suspended_app_cannot_be_deleted(
    client, db_session, user_credentials
):
    """Suspension would mean nothing if the owner could delete and re-add."""
    headers, user_id = await _signup(client, user_credentials)
    repository = await _make_app(db_session, user_id)
    deployment = await _add_deployment(
        db_session, repository, status=DeploymentStatus.STOPPED
    )
    deployment.suspended_by_admin = True
    await db_session.commit()

    res = await client.delete(f"/apps/{repository.id}", headers=headers)
    assert res.status_code == 409
    assert len((await client.get("/apps", headers=headers)).json()) == 1
