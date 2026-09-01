"""
Deployment routes — reading deployments and their build output.

Deployments are created by the analysis step in `repository_routes.py`, and
builds are started there too; this module only reads them back.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.errors import NotFoundError
from app.db import get_db
from app.models.deployment import Deployment
from app.models.repository import Repository
from app.schemas.deployment import BuildLogsOut, DeploymentOut

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
        image_ref=deployment.image_ref,
        build_started_at=deployment.build_started_at,
        build_finished_at=deployment.build_finished_at,
        error_message=deployment.error_message,
        has_logs=bool(deployment.logs_ref),
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


async def _owned_deployment(
    db: AsyncSession, deployment_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Deployment, Repository]:
    """Load a deployment with its repository, scoped to the caller."""
    row = (
        await db.execute(
            select(Deployment, Repository)
            .join(Repository, Deployment.repository_id == Repository.id)
            .where(Deployment.id == deployment_id, Deployment.user_id == user_id)
        )
    ).first()
    if row is None:
        raise NotFoundError("Deployment not found.")
    return row[0], row[1]


@router.get("/{deployment_id}", response_model=DeploymentOut)
async def get_deployment(
    deployment_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> DeploymentOut:
    """One deployment. Polled by the UI while a build is running."""
    deployment, repository = await _owned_deployment(db, deployment_id, current_user.id)
    return _deployment_out(deployment, repository)


# A build log is a few hundred KB at most; only the tail is ever useful.
MAX_LOG_BYTES = 256 * 1024


@router.get("/{deployment_id}/logs", response_model=BuildLogsOut)
async def get_build_logs(
    deployment_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> BuildLogsOut:
    """
    The build output produced so far.

    Reads the log file `logs_ref` points at. A missing file is not an error —
    a queued build simply has nothing to show yet.
    """
    deployment, _ = await _owned_deployment(db, deployment_id, current_user.id)

    text = ""
    truncated = False
    if deployment.logs_ref:
        path = Path(deployment.logs_ref)
        try:
            if path.is_file():
                size = path.stat().st_size
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    if size > MAX_LOG_BYTES:
                        handle.seek(size - MAX_LOG_BYTES)
                        truncated = True
                    text = handle.read()
        except OSError as exc:
            text = f"(build log unavailable: {exc})"

    return BuildLogsOut(
        deployment_id=deployment.id,
        status=deployment.status,
        logs=text,
        truncated=truncated,
    )
