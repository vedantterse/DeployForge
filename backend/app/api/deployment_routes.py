"""
Deployment routes — reading deployments and their build output.

Deployments are created by the analysis step in `repository_routes.py`, and
builds are started there too; this module only reads them back.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.errors import ConflictError, NotFoundError
from app.db import get_db
from app.models.deployment import Deployment
from app.models.event import DeploymentEvent
from app.models.repository import Repository
from app.runtime import docker
from app.runtime import service as runtime_service
from app.schemas.deployment import (
    BuildLogsOut,
    DeploymentEventOut,
    DeploymentOut,
    RuntimeLogsOut,
)

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
        url=deployment.url,
        subdomain=deployment.subdomain,
        app_port=deployment.app_port,
        container_name=deployment.container_name,
        runtime_started_at=deployment.runtime_started_at,
        runtime_stopped_at=deployment.runtime_stopped_at,
        suspended_by_admin=deployment.suspended_by_admin,
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


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
# Starting and stopping happen inline rather than as background tasks: both
# take a second or two, and the user is watching a button. A build is minutes,
# which is why that one is backgrounded and polled.


@router.post("/{deployment_id}/start", response_model=DeploymentOut)
async def start_deployment(
    deployment_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> DeploymentOut:
    """
    Run this deployment's image and publish it at its URL.

    Enforces the account's running-app quota, and refuses while a build or an
    earlier start is still in flight.
    """
    deployment, repository = await _owned_deployment(db, deployment_id, current_user.id)
    if deployment.status.is_busy:
        raise ConflictError(
            f"This deployment is {deployment.status.value}. Wait for it to finish."
        )

    await runtime_service.start(db, deployment, repository, current_user)
    return _deployment_out(deployment, repository)


@router.post("/{deployment_id}/stop", response_model=DeploymentOut)
async def stop_deployment(
    deployment_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> DeploymentOut:
    """Stop the app and take it off the router. Idempotent."""
    deployment, repository = await _owned_deployment(db, deployment_id, current_user.id)
    await runtime_service.stop(db, deployment)
    return _deployment_out(deployment, repository)


@router.post("/{deployment_id}/restart", response_model=DeploymentOut)
async def restart_deployment(
    deployment_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> DeploymentOut:
    """Stop and start again, keeping the same image and the same URL."""
    deployment, repository = await _owned_deployment(db, deployment_id, current_user.id)
    if deployment.status.is_busy:
        raise ConflictError(
            f"This deployment is {deployment.status.value}. Wait for it to finish."
        )

    await runtime_service.restart(db, deployment, repository, current_user)
    return _deployment_out(deployment, repository)


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Response:
    """Stop the app, remove its container, and delete the record."""
    deployment, _ = await _owned_deployment(db, deployment_id, current_user.id)
    await runtime_service.destroy(db, deployment)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{deployment_id}/runtime-logs", response_model=RuntimeLogsOut)
async def get_runtime_logs(
    deployment_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    tail: Annotated[int, Query(ge=10, le=2000)] = 500,
) -> RuntimeLogsOut:
    """
    What the running app has printed.

    Distinct from the build log: that one says why an image could not be
    produced, this one says why the app it produced will not stay up. A
    container that has exited still has logs, which is exactly when they
    matter most.
    """
    deployment, _ = await _owned_deployment(db, deployment_id, current_user.id)

    logs = ""
    running = False
    if deployment.container_name:
        state = await docker.container_state(deployment.container_name)
        running = bool(state and state.get("Running"))
        if state is not None:
            logs = await docker.container_logs(deployment.container_name, tail=tail)
        else:
            logs = "(no container — this deployment is not running)"

    return RuntimeLogsOut(
        deployment_id=deployment.id,
        status=deployment.status,
        logs=logs,
        running=running,
    )


@router.get("/{deployment_id}/events", response_model=list[DeploymentEventOut])
async def get_events(
    deployment_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> list[DeploymentEventOut]:
    """The deployment's timeline, oldest first."""
    await _owned_deployment(db, deployment_id, current_user.id)
    rows = (
        await db.execute(
            select(DeploymentEvent)
            .where(DeploymentEvent.deployment_id == deployment_id)
            .order_by(DeploymentEvent.created_at, DeploymentEvent.id)
        )
    ).scalars().all()
    return [DeploymentEventOut.model_validate(e, from_attributes=True) for e in rows]
