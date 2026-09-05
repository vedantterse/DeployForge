"""
Tests for administrator control and the deploy-once guards.

These encode rules that are easy to state and easy to break: a blocked student
must be blocked at the API and not merely in the UI, and a suspension must not
be escapable by deleting the deployment and starting again. Both are checked
here from the outside, through HTTP, because that is where a real bypass would
happen.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.deployment import BuildMethod, Deployment, DeploymentStatus
from app.models.repository import DetectedType, Repository
from app.models.user import User, UserRole


async def _make_admin(db, client, credentials) -> tuple[str, dict]:
    """Sign up an account, promote it, and return its id and auth header."""
    res = await client.post("/auth/signup", json=credentials)
    token = res.json()["access_token"]
    user_id = uuid.UUID(res.json()["user"]["id"])

    user = await db.get(User, user_id)
    user.role = UserRole.ADMIN
    await db.commit()

    return str(user_id), {"Authorization": f"Bearer {token}"}


async def _deployment_for(db, user_id, **kwargs) -> Deployment:
    repository = Repository(
        user_id=user_id, github_repo_id=kwargs.pop("github_repo_id", 5150),
        name="todo", full_name="octocat/todo", default_branch="main",
        clone_url="https://github.com/octocat/todo.git",
        detected_type=DetectedType.DOCKER,
        deploy_path=kwargs.pop("deploy_path", None),
    )
    db.add(repository)
    await db.commit()
    await db.refresh(repository)

    deployment = Deployment(
        repository_id=repository.id, user_id=user_id,
        build_method=BuildMethod.DOCKER,
        status=kwargs.pop("status", DeploymentStatus.BUILT),
        image_ref="localhost:5000/deployforge/x-todo:abc1234",
        **kwargs,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)
    return deployment


# --- Blocking a student's deploy rights --------------------------------------

@pytest.mark.asyncio
async def test_an_admin_can_revoke_deploy_permission(
    client, db_session, user_credentials, admin_credentials
):
    student = await client.post("/auth/signup", json=user_credentials)
    student_id = student.json()["user"]["id"]
    _, admin_auth = await _make_admin(db_session, client, admin_credentials)

    res = await client.patch(
        f"/admin/users/{student_id}",
        json={"can_deploy": False, "deploy_block_reason": "Crash looping"},
        headers=admin_auth,
    )
    assert res.status_code == 200
    assert res.json()["can_deploy"] is False
    assert res.json()["deploy_block_reason"] == "Crash looping"


@pytest.mark.asyncio
async def test_a_blocked_student_cannot_start_a_build(
    client, db_session, user_credentials
):
    """The block has to hold at the API, not only in the interface."""
    res = await client.post("/auth/signup", json=user_credentials)
    token = res.json()["access_token"]
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment = await _deployment_for(db_session, user_id)

    user = await db_session.get(User, user_id)
    user.can_deploy = False
    user.deploy_block_reason = "Too many failed builds"
    await db_session.commit()

    res = await client.post(
        f"/repos/{deployment.repository_id}/build",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert "Too many failed builds" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_a_blocked_student_can_still_read_their_deployments(
    client, db_session, user_credentials
):
    """Blocking deploys is not the same as taking the account away."""
    res = await client.post("/auth/signup", json=user_credentials)
    token = res.json()["access_token"]
    user_id = uuid.UUID(res.json()["user"]["id"])
    await _deployment_for(db_session, user_id)

    user = await db_session.get(User, user_id)
    user.can_deploy = False
    await db_session.commit()

    res = await client.get(
        "/deployments", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert len(res.json()) == 1


@pytest.mark.asyncio
async def test_an_admin_cannot_revoke_their_own_deploy_permission(
    client, db_session, admin_credentials
):
    admin_id, admin_auth = await _make_admin(db_session, client, admin_credentials)

    res = await client.patch(
        f"/admin/users/{admin_id}", json={"can_deploy": False}, headers=admin_auth
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_restoring_permission_clears_the_reason(
    client, db_session, user_credentials, admin_credentials
):
    """A stale reason must not be inherited by the next block."""
    student = await client.post("/auth/signup", json=user_credentials)
    student_id = student.json()["user"]["id"]
    _, admin_auth = await _make_admin(db_session, client, admin_credentials)

    await client.patch(
        f"/admin/users/{student_id}",
        json={"can_deploy": False, "deploy_block_reason": "Old reason"},
        headers=admin_auth,
    )
    res = await client.patch(
        f"/admin/users/{student_id}", json={"can_deploy": True}, headers=admin_auth
    )
    assert res.json()["can_deploy"] is True
    assert res.json()["deploy_block_reason"] is None


# --- Suspension cannot be escaped --------------------------------------------

@pytest.mark.asyncio
async def test_a_suspended_deployment_cannot_be_deleted_by_its_owner(
    client, db_session, user_credentials
):
    """
    Otherwise suspension is meaningless: delete it, reconnect the repository,
    and you have a clean deployment a moment later.
    """
    res = await client.post("/auth/signup", json=user_credentials)
    token = res.json()["access_token"]
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment = await _deployment_for(
        db_session, user_id, status=DeploymentStatus.STOPPED,
        suspended_by_admin=True, suspension_reason="Mining crypto",
    )

    res = await client.delete(
        f"/deployments/{deployment.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 409
    assert "administrator" in res.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_an_unsuspended_deployment_can_be_deleted(
    client, db_session, user_credentials, monkeypatch
):
    from app.runtime import service as runtime

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(runtime.docker, "stop_container", noop)
    monkeypatch.setattr(runtime.docker, "remove_container", noop)

    res = await client.post("/auth/signup", json=user_credentials)
    token = res.json()["access_token"]
    user_id = uuid.UUID(res.json()["user"]["id"])
    deployment = await _deployment_for(db_session, user_id)

    res = await client.delete(
        f"/deployments/{deployment.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_suspending_records_the_reason_for_the_owner(
    client, db_session, user_credentials, admin_credentials, monkeypatch
):
    from app.runtime import service as runtime

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(runtime.docker, "stop_container", noop)
    monkeypatch.setattr(runtime.docker, "remove_container", noop)

    student = await client.post("/auth/signup", json=user_credentials)
    student_id = uuid.UUID(student.json()["user"]["id"])
    deployment = await _deployment_for(
        db_session, student_id, status=DeploymentStatus.RUNNING,
        subdomain="todo-aaa111", container_name="df-aaa111", app_port=3000,
    )
    _, admin_auth = await _make_admin(db_session, client, admin_credentials)

    res = await client.post(
        f"/admin/deployments/{deployment.id}/suspend",
        json={"reason": "Using too much memory"},
        headers=admin_auth,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["suspended_by_admin"] is True
    assert body["suspension_reason"] == "Using too much memory"
    assert body["status"] == "stopped"


# --- Deploy once --------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_same_target_cannot_be_connected_twice(
    client, db_session, user_credentials
):
    """The database constraint is the backstop behind the greyed-out button."""
    from sqlalchemy.exc import IntegrityError

    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    await _deployment_for(db_session, user_id, github_repo_id=777)

    duplicate = Repository(
        user_id=user_id, github_repo_id=777, name="todo",
        full_name="octocat/todo", default_branch="main",
        clone_url="https://github.com/octocat/todo.git",
        deploy_path=None,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_a_monorepos_other_directories_stay_available(
    client, db_session, user_credentials
):
    """Connecting `frontend/` must not consume `backend/` too."""
    res = await client.post("/auth/signup", json=user_credentials)
    user_id = uuid.UUID(res.json()["user"]["id"])
    await _deployment_for(db_session, user_id, github_repo_id=888, deploy_path="frontend")

    backend = Repository(
        user_id=user_id, github_repo_id=888, name="todo",
        full_name="octocat/todo", default_branch="main",
        clone_url="https://github.com/octocat/todo.git",
        deploy_path="backend",
    )
    db_session.add(backend)
    await db_session.commit()  # must not raise

    assert backend.id is not None
