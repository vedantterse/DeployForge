"""
Deployment routes.

Phase 1 only reads deployments — they are created by the analysis step in
`repository_routes.py`. Nothing here builds or runs anything.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db import get_db
from app.models.deployment import Deployment
from app.models.repository import Repository
from app.schemas.deployment import DeploymentOut

router = APIRouter(prefix="/deployments", tags=["deployments"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _deployment_out(
    deployment: Deployment,
    repository: Repository,
    *,
    user_email: str | None = None,
) -> DeploymentOut:
    return DeploymentOut(
        id=deployment.id,
        status=deployment.status,
        build_method=deployment.build_method,
        commit_sha=deployment.commit_sha,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
        repository_id=repository.id,
        full_name=repository.full_name,
        deploy_path=repository.deploy_path,
        target_label=repository.target_label,
        detected_type=repository.detected_type,
        detected_framework=repository.detected_framework,
        user_id=deployment.user_id if user_email else None,
        user_email=user_email,
    )


@router.get("", response_model=list[DeploymentOut])
async def list_my_deployments(
    current_user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[DeploymentOut]:
    """This user's deployments, newest first."""
    rows = await db.execute(
        select(Deployment, Repository)
        .join(Repository, Deployment.repository_id == Repository.id)
        .where(Deployment.user_id == current_user.id)
        # id breaks ties so paging is stable when timestamps match
        .order_by(Deployment.created_at.desc(), Deployment.id.desc())
        .limit(limit)
    )
    return [_deployment_out(d, r) for d, r in rows.all()]
