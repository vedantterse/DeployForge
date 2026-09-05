"""
The app lifecycle: start, stop, restart, destroy.

Building produces an image; this is what turns an image into something a
student can open in a browser. It owns the container, the subdomain, and the
runtime columns on `Deployment` — the router reads those rows to build its
configuration (see `api/internal_routes.py`), so writing them here *is* the
act of publishing the app.

Every operation is idempotent and records a `DeploymentEvent`. A container
that is already gone is a successful stop; a container that already exists is
replaced rather than fought with.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.crypto import decrypt_value
from app.core.errors import AppError
from app.models.deployment import Deployment, DeploymentStatus
from app.models.environment import EnvironmentVariable
from app.models.event import DeploymentEvent, EventLevel
from app.models.repository import Repository
from app.models.user import User
from app.runtime import docker, naming, ports

logger = logging.getLogger(__name__)


class RuntimeError_(AppError):
    """The app could not be started or stopped."""

    code = "runtime_error"
    status_code = 409


class QuotaExceededError(AppError):
    code = "quota_exceeded"
    status_code = 409


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------

async def record(
    db: AsyncSession,
    deployment_id: uuid.UUID,
    stage: str,
    message: str,
    *,
    level: EventLevel = EventLevel.INFO,
    actor: str | None = None,
    commit: bool = True,
) -> None:
    """
    Append one line to a deployment's timeline.

    Never raises: a deployment must not fail because its audit trail could not
    be written.
    """
    try:
        db.add(
            DeploymentEvent(
                deployment_id=deployment_id,
                stage=stage,
                message=message[:2000],
                level=level,
                actor=actor,
            )
        )
        if commit:
            await db.commit()
    except Exception:  # noqa: BLE001 — the timeline is not worth a failure
        logger.warning("Could not record %s event for %s", stage, deployment_id)


# --------------------------------------------------------------------------
# Quota
# --------------------------------------------------------------------------

async def running_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    """How many of this user's apps are currently running."""
    return (
        await db.execute(
            select(func.count())
            .select_from(Deployment)
            .where(
                Deployment.user_id == user_id,
                Deployment.status.in_(
                    [DeploymentStatus.RUNNING, DeploymentStatus.LIVE]
                ),
            )
        )
    ).scalar_one()


async def check_quota(
    db: AsyncSession, user: User, *, excluding: uuid.UUID | None = None
) -> None:
    """
    Refuse to start another app when the user is at their limit.

    `excluding` skips the deployment being restarted, which already holds one
    of the user's slots and must not be counted against itself.
    """
    stmt = select(func.count()).select_from(Deployment).where(
        Deployment.user_id == user.id,
        Deployment.status.in_([DeploymentStatus.RUNNING, DeploymentStatus.LIVE]),
    )
    if excluding is not None:
        stmt = stmt.where(Deployment.id != excluding)
    running = (await db.execute(stmt)).scalar_one()

    if running >= user.max_deployments:
        raise QuotaExceededError(
            f"You already have {running} of {user.max_deployments} apps running. "
            "Stop one before starting another, or ask an administrator to raise "
            "your limit."
        )


# --------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------

async def environment_for(db: AsyncSession, repository_id: uuid.UUID) -> dict[str, str]:
    """Decrypt this target's environment variables. A broken value is skipped."""
    rows = (
        await db.execute(
            select(EnvironmentVariable).where(
                EnvironmentVariable.repository_id == repository_id
            )
        )
    ).scalars().all()

    env: dict[str, str] = {}
    for row in rows:
        try:
            env[row.key] = decrypt_value(row.value_enc)
        except Exception:  # noqa: BLE001 — one bad value must not block a start
            logger.warning("Skipping unreadable environment variable %s", row.key)
    return env


# --------------------------------------------------------------------------
# Start
# --------------------------------------------------------------------------

async def start(
    db: AsyncSession,
    deployment: Deployment,
    repository: Repository,
    user: User,
    *,
    actor: str = "owner",
) -> Deployment:
    """
    Run the built image and publish it at its URL.

    Replaces any existing container for this deployment rather than refusing:
    "start" means "be running now", and a leftover container from a previous
    attempt is an implementation detail the student should not have to know
    about.
    """
    if deployment.image_ref is None:
        raise RuntimeError_(
            "This deployment has no image yet. Build it before starting it."
        )
    if deployment.suspended_by_admin and actor != "admin":
        raise RuntimeError_(
            "An administrator has suspended this deployment. Contact them to "
            "have it resumed."
        )

    await check_quota(db, user, excluding=deployment.id)

    if not await docker.daemon_available():
        raise RuntimeError_("The Docker daemon is not reachable on the server.")
    await docker.ensure_network()

    # Names are assigned once and then reused, so a restart keeps the URL the
    # student has already shared.
    if not deployment.subdomain:
        deployment.subdomain = naming.subdomain_for(
            deployment_id=deployment.id,
            repository_name=repository.name,
            deploy_path=repository.deploy_path,
        )
    container = deployment.container_name or naming.container_name_for(deployment.id)
    deployment.container_name = container

    env = await environment_for(db, repository.id)
    exposed = await docker.image_exposed_ports(deployment.image_ref)
    port = ports.choose_port(
        exposed_ports=exposed,
        env=env,
        framework=repository.detected_framework,
        build_method=deployment.build_method.value if deployment.build_method else None,
    )
    deployment.app_port = port

    deployment.status = DeploymentStatus.STARTING
    deployment.error_message = None
    await db.commit()

    await record(
        db,
        deployment.id,
        "start",
        f"Starting {deployment.image_ref} on port {port}.",
        actor=actor,
    )

    # A container from a previous run would take the name; replace it.
    await docker.remove_container(container)

    # Buildpack launchers and most frameworks read PORT. Setting it makes the
    # app listen where the router expects, instead of hoping the two agree.
    run_env = {"PORT": str(port), **env}

    result = await docker.run_container(
        name=container,
        image_ref=deployment.image_ref,
        port=port,
        env=run_env,
        labels={
            "deployforge.deployment": str(deployment.id),
            "deployforge.owner": str(deployment.user_id),
        },
    )

    if not result.ok:
        await _fail(db, deployment, f"Could not start the container: {result.message}")
        raise RuntimeError_(f"Could not start the container: {result.message}")

    deployment.container_id = result.stdout.strip()[:64] or None

    # A container that exits immediately — a crash on boot, a bad start command
    # — is the most common failure, and "running" would be a lie. Give it a
    # moment, then check it is still alive.
    await asyncio.sleep(settings.app_start_grace_seconds)
    state = await docker.container_state(container)

    if not state or not state.get("Running"):
        logs = await docker.container_logs(container, tail=40)
        exit_code = (state or {}).get("ExitCode")
        await _fail(
            db,
            deployment,
            f"The container exited immediately (exit code {exit_code}). "
            "Check the runtime log for what the app printed as it died.",
        )
        await record(
            db,
            deployment.id,
            "start",
            f"Container exited on boot. Last output:\n{logs[-1500:]}",
            level=EventLevel.ERROR,
        )
        raise RuntimeError_(
            f"The app started and then exited (exit code {exit_code}). "
            "Its output is in the runtime log."
        )

    deployment.status = DeploymentStatus.RUNNING
    deployment.runtime_started_at = datetime.now(timezone.utc)
    deployment.runtime_stopped_at = None
    deployment.error_message = None
    await db.commit()

    await record(
        db,
        deployment.id,
        "start",
        f"Running at {deployment.url}",
        level=EventLevel.SUCCESS,
        actor=actor,
    )
    return deployment


async def _fail(db: AsyncSession, deployment: Deployment, message: str) -> None:
    deployment.status = DeploymentStatus.FAILED
    deployment.error_message = message
    deployment.runtime_stopped_at = datetime.now(timezone.utc)
    await db.commit()


# --------------------------------------------------------------------------
# Stop / restart / destroy
# --------------------------------------------------------------------------

async def stop(
    db: AsyncSession,
    deployment: Deployment,
    *,
    actor: str = "owner",
    suspend: bool = False,
) -> Deployment:
    """
    Stop the app and take it off the router.

    A container that is already gone is success — the caller asked for it to
    not be running, and it is not running.
    """
    container = deployment.container_name
    if container:
        await docker.stop_container(container)
        await docker.remove_container(container)

    deployment.status = DeploymentStatus.STOPPED
    deployment.container_id = None
    deployment.runtime_stopped_at = datetime.now(timezone.utc)
    if suspend:
        deployment.suspended_by_admin = True
    await db.commit()

    await record(
        db,
        deployment.id,
        "stop",
        "Suspended by an administrator." if suspend else "Stopped.",
        level=EventLevel.WARNING if suspend else EventLevel.INFO,
        actor=actor,
    )
    return deployment


async def restart(
    db: AsyncSession,
    deployment: Deployment,
    repository: Repository,
    user: User,
    *,
    actor: str = "owner",
) -> Deployment:
    """Stop and start again, on the same image and the same URL."""
    if deployment.container_name:
        await docker.stop_container(deployment.container_name)
        await docker.remove_container(deployment.container_name)
    return await start(db, deployment, repository, user, actor=actor)


async def destroy(
    db: AsyncSession, deployment: Deployment, *, actor: str = "owner"
) -> None:
    """
    Remove the container and forget the deployment.

    The image is left in the registry on purpose: it is the artifact of a
    build, other deployments may reference the same tag, and deleting it would
    make a redeploy re-run the whole build for no gain.
    """
    if deployment.container_name:
        await docker.stop_container(deployment.container_name)
        await docker.remove_container(deployment.container_name)

    await db.delete(deployment)
    await db.commit()


# --------------------------------------------------------------------------
# Reconciliation
# --------------------------------------------------------------------------

async def reconcile(db: AsyncSession) -> int:
    """
    Make the database agree with what Docker is actually running.

    The platform's rows outlive the process that wrote them: Docker Desktop
    restarts, the machine reboots, a student stops a container by hand. Without
    this, the dashboard confidently shows apps as running that are not, and the
    router advertises routes to containers that no longer exist.

    Called at startup. Returns how many rows it corrected.
    """
    rows = (
        await db.execute(
            select(Deployment).where(
                Deployment.status.in_(
                    [
                        DeploymentStatus.RUNNING,
                        DeploymentStatus.LIVE,
                        DeploymentStatus.STARTING,
                    ]
                )
            )
        )
    ).scalars().all()

    if not rows:
        return 0
    if not await docker.daemon_available():
        logger.warning("Docker unreachable; skipping reconciliation")
        return 0

    corrected = 0
    for deployment in rows:
        state = (
            await docker.container_state(deployment.container_name)
            if deployment.container_name
            else None
        )
        if state and state.get("Running"):
            # A build or start that was interrupted mid-flight is now healthy.
            if deployment.status is DeploymentStatus.STARTING:
                deployment.status = DeploymentStatus.RUNNING
                corrected += 1
            continue

        deployment.status = DeploymentStatus.STOPPED
        deployment.container_id = None
        deployment.runtime_stopped_at = datetime.now(timezone.utc)
        corrected += 1
        await record(
            db,
            deployment.id,
            "reconcile",
            "Marked stopped: no running container was found for it.",
            level=EventLevel.WARNING,
            commit=False,
        )

    if corrected:
        await db.commit()
        logger.info("Reconciled %d deployment(s) against Docker", corrected)
    return corrected
