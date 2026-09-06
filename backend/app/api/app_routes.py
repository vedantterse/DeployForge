"""
App routes — the student's own view of what they have deployed.

`deployment_routes.py` reads individual build attempts. This module reads the
thing those attempts belong to. The database already modelled it correctly —
one `repositories` row per connected target, many `deployments` rows beneath
it — but nothing exposed that shape, so the UI listed build attempts and a
redeploy looked like a second app.

Nothing here starts, stops or builds anything: an app has no lifecycle of its
own, only the lifecycle of its current deployment.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.errors import ConflictError, NotFoundError
from app.db import get_db
from app.models.deployment import Deployment, DeploymentStatus
from app.models.repository import Repository
from app.runtime import service as runtime_service
from app.schemas.app import AppDetailOut, AppOut
from app.api.deployment_routes import deployment_out

router = APIRouter(prefix="/apps", tags=["apps"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

# An app is "up" when one of its deployments is.
_LIVE = (DeploymentStatus.RUNNING, DeploymentStatus.LIVE)

# Statuses that mean the build produced something usable.
_SUCCEEDED = (
    DeploymentStatus.BUILT,
    DeploymentStatus.STARTING,
    DeploymentStatus.RUNNING,
    DeploymentStatus.LIVE,
    DeploymentStatus.STOPPED,
)


def _current(deployments: list[Deployment]) -> Deployment | None:
    """
    Which deployment the app currently *is*, given its history newest first.

    A running deployment wins over a newer failed one: if a student redeploys
    and the build fails, their app is still up and saying otherwise would be
    false. Otherwise the newest attempt is the current state of affairs —
    including when it failed, because that is what they need to look at.
    """
    for deployment in deployments:
        if deployment.status in _LIVE:
            return deployment
    return deployments[0] if deployments else None


def _app_out(
    repository: Repository, deployments: list[Deployment], *, detail: bool = False
) -> AppOut:
    """Build the response for one app from its deployments, newest first."""
    current = _current(deployments)
    succeeded = [d for d in deployments if d.status in _SUCCEEDED]

    fields = dict(
        id=repository.id,
        name=repository.name,
        full_name=repository.full_name,
        target_label=repository.target_label,
        deploy_path=repository.deploy_path,
        service_paths=repository.service_paths,
        is_multi_service=repository.is_multi_service,
        detected_type=repository.detected_type,
        detected_framework=repository.detected_framework,
        created_at=repository.created_at,
        updated_at=repository.updated_at,
        current=deployment_out(current, repository) if current else None,
        # An app connected but never built has one `analyzed` row, which is
        # bookkeeping rather than something the student did. Counting it would
        # tell them they have a deployment when they have never deployed.
        deployment_count=sum(
            1 for d in deployments if d.status is not DeploymentStatus.ANALYZED
        ),
        last_deployed_at=(
            succeeded[0].build_finished_at or succeeded[0].created_at
            if succeeded
            else None
        ),
    )
    if not detail:
        return AppOut(**fields)
    return AppDetailOut(
        **fields,
        deployments=[
            deployment_out(d, repository)
            for d in deployments
            if d.status is not DeploymentStatus.ANALYZED
        ],
    )


async def _owned_app(
    db: AsyncSession, app_id: uuid.UUID, user_id: uuid.UUID
) -> Repository:
    repository = (
        await db.execute(
            select(Repository).where(
                Repository.id == app_id, Repository.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if repository is None:
        raise NotFoundError("App not found.")
    return repository


async def _deployments_for(
    db: AsyncSession, repository_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[Deployment]]:
    """Every deployment of the given apps, newest first within each app."""
    if not repository_ids:
        return {}
    rows = (
        await db.execute(
            select(Deployment)
            .where(Deployment.repository_id.in_(repository_ids))
            # id breaks ties so the order is stable when two rows share a
            # timestamp, which they do when a build is queued and started in
            # the same instant.
            .order_by(Deployment.created_at.desc(), Deployment.id.desc())
        )
    ).scalars().all()

    grouped: dict[uuid.UUID, list[Deployment]] = {rid: [] for rid in repository_ids}
    for deployment in rows:
        grouped[deployment.repository_id].append(deployment)
    return grouped


@router.get("", response_model=list[AppOut])
async def list_my_apps(current_user: CurrentUser, db: DbSession) -> list[AppOut]:
    """
    Every app this student has connected, most recently touched first.

    Two queries regardless of how many apps there are, rather than one per app.
    """
    repositories = (
        await db.execute(
            select(Repository)
            .where(Repository.user_id == current_user.id)
            .order_by(Repository.created_at.desc())
        )
    ).scalars().all()

    grouped = await _deployments_for(db, [r.id for r in repositories])
    return [_app_out(r, grouped.get(r.id, [])) for r in repositories]


@router.get("/{app_id}", response_model=AppDetailOut)
async def get_app(
    app_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> AppDetailOut:
    """One app and every deployment of it. Polled while a build is running."""
    repository = await _owned_app(db, app_id, current_user.id)
    grouped = await _deployments_for(db, [repository.id])
    return _app_out(repository, grouped.get(repository.id, []), detail=True)  # type: ignore[return-value]


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app(
    app_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> Response:
    """
    Remove the app: every container it is running, every deployment record,
    and the connection to the repository itself.

    Deleting the deployments alone would leave the repository connected but
    invisible — nothing would list it, and reconnecting it would collide with
    the row still holding its place. So the app goes as a whole, and the
    repository becomes available to connect again.

    Refused while an administrator has any of it suspended: otherwise the owner
    could delete a suspended app, reconnect the same repository and have a
    clean one a moment later, which would make suspension meaningless.
    """
    repository = await _owned_app(db, app_id, current_user.id)
    deployments = (
        await db.execute(
            select(Deployment).where(Deployment.repository_id == repository.id)
        )
    ).scalars().all()

    if any(d.suspended_by_admin for d in deployments):
        raise ConflictError(
            "This app has been suspended by an administrator and cannot be "
            "deleted. Contact them if you think that is a mistake."
        )

    for deployment in deployments:
        await runtime_service.destroy(db, deployment)

    await db.delete(repository)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
