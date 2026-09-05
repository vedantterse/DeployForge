"""
Admin-only routes.

Every route here depends on `require_admin`, so an authenticated non-admin gets
403 and an anonymous caller gets 401 — the same auth system as everywhere else,
gated on `User.role`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deployment_routes import _deployment_out
from app.auth.dependencies import AdminUser
from app.builder import pack
from app.config import settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.db import get_db
from app.models.deployment import Deployment, DeploymentStatus
from app.models.github import GitHubConnection
from app.models.repository import Repository
from app.models.user import User, UserRole
from app.runtime import docker as docker_runtime
from app.runtime import service as runtime_service
from app.schemas.auth import UserOut
from app.schemas.deployment import (
    AdminUserUpdate,
    DeploymentOut,
    PlatformStatusOut,
    UserDeploymentsOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/users", response_model=list[UserOut])
async def list_users(_admin: AdminUser, db: DbSession) -> list[UserOut]:
    """Every account on the platform, newest first."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.get("/deployments", response_model=list[DeploymentOut])
async def list_all_deployments(
    _admin: AdminUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[DeploymentOut]:
    """Every deployment on the platform, newest first, with its owner's email."""
    rows = await db.execute(
        select(Deployment, Repository, User.email)
        .join(Repository, Deployment.repository_id == Repository.id)
        .join(User, Deployment.user_id == User.id)
        .order_by(Deployment.created_at.desc(), Deployment.id.desc())
        .limit(limit)
    )
    return [
        _deployment_out(d, r, user_email=email) for d, r, email in rows.all()
    ]


@router.get("/overview", response_model=list[UserDeploymentsOut])
async def platform_overview(_admin: AdminUser, db: DbSession) -> list[UserDeploymentsOut]:
    """
    Every account with its deployments — the admin dashboard.

    One query per table rather than per user, then grouped in memory, so the
    page cost does not grow with the number of accounts.
    """
    users = (
        await db.execute(select(User).order_by(User.created_at.desc()))
    ).scalars().all()

    rows = (
        await db.execute(
            select(Deployment, Repository)
            .join(Repository, Deployment.repository_id == Repository.id)
            .order_by(Deployment.created_at.desc(), Deployment.id.desc())
        )
    ).all()

    repo_counts: dict = {}
    for user_id, count in (
        await db.execute(
            select(Repository.user_id, func.count())
            .group_by(Repository.user_id)
        )
    ).all():
        repo_counts[user_id] = count

    connections = {
        c.user_id: c.github_username
        for c in (await db.execute(select(GitHubConnection))).scalars().all()
    }

    by_user: dict = {}
    running_by_user: dict = {}
    for deployment, repository in rows:
        by_user.setdefault(deployment.user_id, []).append(
            _deployment_out(deployment, repository, user_email=None)
        )
        if deployment.status.is_running:
            running_by_user[deployment.user_id] = (
                running_by_user.get(deployment.user_id, 0) + 1
            )

    return [
        UserDeploymentsOut(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            deployment_count=len(by_user.get(user.id, [])),
            repository_count=repo_counts.get(user.id, 0),
            running_count=running_by_user.get(user.id, 0),
            max_deployments=user.max_deployments,
            github_username=connections.get(user.id),
            deployments=by_user.get(user.id, []),
        )
        for user in users
    ]


@router.get("/stats")
async def platform_stats(_admin: AdminUser, db: DbSession) -> dict:
    """Row counts across the platform — a small admin-only dashboard."""

    async def count(model, *where) -> int:
        stmt = select(func.count()).select_from(model)
        if where:
            stmt = stmt.where(*where)
        return (await db.execute(stmt)).scalar_one()

    return {
        "users": await count(User),
        "admins": await count(User, User.role == UserRole.ADMIN),
        "github_connections": await count(GitHubConnection),
        "repositories": await count(Repository),
        "deployments": await count(Deployment),
        "running": await count(
            Deployment,
            Deployment.status.in_([DeploymentStatus.RUNNING, DeploymentStatus.LIVE]),
        ),
        "failed": await count(Deployment, Deployment.status == DeploymentStatus.FAILED),
    }


# ---------------------------------------------------------------------------
# Control
# ---------------------------------------------------------------------------
# An admin runs the one machine every student's app shares, so these are the
# levers that stop a single account from spoiling it for everyone: suspend a
# misbehaving app, change what an account may do, or disable it outright.


async def _deployment_with_context(
    db: AsyncSession, deployment_id: uuid.UUID
) -> tuple[Deployment, Repository, User]:
    """Load any deployment on the platform — admins are not scoped to their own."""
    row = (
        await db.execute(
            select(Deployment, Repository, User)
            .join(Repository, Deployment.repository_id == Repository.id)
            .join(User, Deployment.user_id == User.id)
            .where(Deployment.id == deployment_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Deployment not found.")
    return row[0], row[1], row[2]


@router.post("/deployments/{deployment_id}/suspend", response_model=DeploymentOut)
async def suspend_deployment(
    deployment_id: uuid.UUID, _admin: AdminUser, db: DbSession
) -> DeploymentOut:
    """
    Stop an app and prevent its owner from starting it again.

    Deliberately distinct from the owner's own stop: this sets
    `suspended_by_admin`, which the start path refuses to override. Without
    that flag, an admin stopping a runaway app would simply be undone by the
    student a second later.
    """
    deployment, repository, owner = await _deployment_with_context(db, deployment_id)
    await runtime_service.stop(db, deployment, actor="admin", suspend=True)
    return _deployment_out(deployment, repository, user_email=owner.email)


@router.post("/deployments/{deployment_id}/resume", response_model=DeploymentOut)
async def resume_deployment(
    deployment_id: uuid.UUID, _admin: AdminUser, db: DbSession
) -> DeploymentOut:
    """Lift a suspension, and start the app again if it has an image."""
    deployment, repository, owner = await _deployment_with_context(db, deployment_id)
    deployment.suspended_by_admin = False
    await db.commit()
    await runtime_service.record(
        db, deployment.id, "resume",
        "Suspension lifted by an administrator.", actor="admin",
    )
    if deployment.image_ref:
        await runtime_service.start(db, deployment, repository, owner, actor="admin")
    return _deployment_out(deployment, repository, user_email=owner.email)


@router.delete("/deployments/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_deployment(
    deployment_id: uuid.UUID, _admin: AdminUser, db: DbSession
) -> Response:
    """Remove any deployment on the platform, along with its container."""
    deployment, _repository, _owner = await _deployment_with_context(db, deployment_id)
    await runtime_service.destroy(db, deployment, actor="admin")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID, payload: AdminUserUpdate, admin: AdminUser, db: DbSession
) -> UserOut:
    """
    Change an account's quota, role, or whether it is enabled.

    An admin may not disable or demote themselves: locking the last
    administrator out of the platform is never the intent, and recovering from
    it takes direct database access.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("Account not found.")

    if user.id == admin.id and (
        payload.is_active is False or payload.role == UserRole.USER
    ):
        raise ConflictError(
            "You cannot remove your own administrator access. Ask another "
            "administrator to do it."
        )

    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.max_deployments is not None:
        user.max_deployments = payload.max_deployments
    if payload.role is not None:
        user.role = payload.role

    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/platform/status", response_model=PlatformStatusOut)
async def platform_status(_admin: AdminUser) -> PlatformStatusOut:
    """
    Whether the infrastructure the platform depends on is actually up.

    Checked live rather than assumed: "your build failed" and "Docker is down"
    look identical to a student, and an admin should be able to tell them apart
    without reading a server log.
    """
    detail: dict[str, str] = {}

    docker_ok = await docker_runtime.daemon_available()
    if not docker_ok:
        detail["docker"] = "The Docker daemon is not responding."

    registry_ok = await _registry_reachable()
    if not registry_ok:
        detail["registry"] = (
            f"No registry at {settings.registry_host}. Builds still work; "
            "images are kept locally instead of being stored."
        )

    router_state = await docker_runtime.container_state(settings.router_container)
    router_ok = bool(router_state and router_state.get("Running"))
    if not router_ok:
        detail["router"] = (
            f"The {settings.router_container} container is not running, so app "
            "URLs will not resolve."
        )

    buildpacks_ok = True
    try:
        await pack.check_toolchain()
    except AppError as exc:
        buildpacks_ok = False
        detail["buildpacks"] = exc.message

    return PlatformStatusOut(
        docker=docker_ok,
        registry=registry_ok,
        router=router_ok,
        buildpacks=buildpacks_ok,
        detail=detail,
    )


async def _registry_reachable() -> bool:
    """True when the image registry answers its version endpoint."""
    if not settings.registry_push:
        return False
    url = f"http://{settings.registry_host.strip().rstrip('/')}/v2/"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        return False
    # 200, or 401 when the registry requires auth. Either way something is
    # listening and speaking the registry protocol.
    return response.status_code in (200, 401)
