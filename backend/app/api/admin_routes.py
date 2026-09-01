"""
Admin-only routes.

Every route here depends on `require_admin`, so an authenticated non-admin gets
403 and an anonymous caller gets 401 — the same auth system as everywhere else,
gated on `User.role`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deployment_routes import _deployment_out
from app.auth.dependencies import AdminUser
from app.db import get_db
from app.models.deployment import Deployment
from app.models.github import GitHubConnection
from app.models.repository import Repository
from app.models.user import User, UserRole
from app.schemas.auth import UserOut
from app.schemas.deployment import DeploymentOut, UserDeploymentsOut

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
    for deployment, repository in rows:
        by_user.setdefault(deployment.user_id, []).append(
            _deployment_out(deployment, repository, user_email=None)
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
    }
