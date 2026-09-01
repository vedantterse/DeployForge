"""
Orchestrate a build: download the repository, run buildpacks, record the result.

The steps are the same ones the analysis flow uses — download to a temp
directory, resolve the chosen target — with the buildpack build in the middle
and the outcome written to the Deployment row.

This runs in the background, outside the HTTP request, so it opens its own
database session and never lets an exception escape: a crashed build must leave
the deployment marked `failed` with a reason, not stuck in `building` forever.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.builder import pack
from app.config import settings
from app.core.crypto import decrypt_value
from app.db import AsyncSessionLocal
from app.detection.candidates import ROOT_PATH, resolve_path
from app.github import client as github_client
from app.github.download import downloaded_repository
from app.github.token import get_access_token
from app.models.deployment import Deployment, DeploymentStatus
from app.models.environment import EnvironmentVariable
from app.models.repository import Repository

logger = logging.getLogger(__name__)


def log_path_for(deployment_id: uuid.UUID) -> Path:
    """Where a deployment's build log lives."""
    base = settings.build_log_dir.strip() or settings.repo_workdir.strip()
    directory = Path(base) / "deployforge-build-logs" if base else Path("/tmp/deployforge-build-logs")
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{deployment_id}.log"


async def _environment_for(db: AsyncSession, repository_id: uuid.UUID) -> dict[str, str]:
    """Decrypt the target's environment variables. A broken value is skipped."""
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
        except Exception:  # noqa: BLE001 — one unreadable value must not kill the build
            logger.warning("Skipping unreadable environment variable %s", row.key)
    return env


async def _finish(
    db: AsyncSession,
    deployment: Deployment,
    *,
    status: DeploymentStatus,
    image_ref: str | None = None,
    error: str | None = None,
) -> None:
    deployment.status = status
    deployment.image_ref = image_ref
    deployment.error_message = error
    deployment.build_finished_at = datetime.now(timezone.utc)
    await db.commit()


async def run_build(
    deployment_id: uuid.UUID, db: AsyncSession | None = None
) -> None:
    """
    Build the image for `deployment_id`.

    Safe to hand to a background task: by default it opens its own session,
    because the request that queued the build has already finished. A session
    can be passed in instead — tests do that so the build sees the same
    transaction they set up.

    Every failure becomes a `failed` deployment with a reason and a log file;
    nothing escapes.
    """
    if db is not None:
        await _run_with_session(db, deployment_id)
        return
    async with AsyncSessionLocal() as own_session:
        await _run_with_session(own_session, deployment_id)


async def _run_with_session(db: AsyncSession, deployment_id: uuid.UUID) -> None:
    deployment = await db.get(Deployment, deployment_id)
    if deployment is None:
        logger.warning("Build requested for unknown deployment %s", deployment_id)
        return

    repository = await db.get(Repository, deployment.repository_id)
    if repository is None:
        await _finish(db, deployment, status=DeploymentStatus.FAILED,
                      error="The repository was removed before the build started.")
        return

    log_file = log_path_for(deployment_id)
    deployment.status = DeploymentStatus.BUILDING
    deployment.build_started_at = datetime.now(timezone.utc)
    deployment.logs_ref = str(log_file)
    deployment.error_message = None
    await db.commit()

    try:
        await _build(db, deployment, repository, log_file)
    except Exception as exc:  # noqa: BLE001 — never leave a build stuck
        logger.exception("Build %s failed unexpectedly", deployment_id)
        _append(log_file, f"\nBuild failed: {type(exc).__name__}: {exc}\n")
        await _finish(
            db,
            deployment,
            status=DeploymentStatus.FAILED,
            error=f"{type(exc).__name__}: {exc}",
        )


async def _build(
    db: AsyncSession,
    deployment: Deployment,
    repository: Repository,
    log_file: Path,
) -> None:
    """The happy path, with each failure recorded rather than raised."""
    if not await pack.docker_available():
        await _finish(
            db, deployment, status=DeploymentStatus.FAILED,
            error="The Docker daemon is not reachable on the server.",
        )
        return

    access_token = await get_access_token(db, repository.user_id)
    commit_sha = (
        await github_client.get_head_commit(
            access_token, repository.full_name, repository.default_branch
        )
        or deployment.commit_sha
    )
    if commit_sha:
        deployment.commit_sha = commit_sha
        await db.commit()

    image_ref = pack.build_image_ref(
        user_id=repository.user_id,
        repository_name=repository.name,
        deploy_path=repository.deploy_path,
        commit_sha=commit_sha,
    )
    env = await _environment_for(db, repository.id)

    _append(
        log_file,
        f"Building {repository.target_label}\n"
        f"  branch     {repository.default_branch}\n"
        f"  commit     {commit_sha or 'unknown'}\n"
        f"  image      {image_ref}\n"
        f"  env vars   {len(env)}\n"
        f"  builder    {settings.pack_builder}\n\n",
    )

    async with downloaded_repository(
        access_token, repository.full_name, repository.default_branch
    ) as download:
        try:
            source = resolve_path(download.path, repository.deploy_path or ROOT_PATH)
        except ValueError as exc:
            await _finish(db, deployment, status=DeploymentStatus.FAILED, error=str(exc))
            return
        if not source.is_dir():
            await _finish(
                db, deployment, status=DeploymentStatus.FAILED,
                error=f"{repository.deploy_path}/ no longer exists in the repository.",
            )
            return

        # The env file lives inside the temp workdir, which is deleted with it.
        env_file = None
        if env:
            env_file = pack.write_env_file(env, download.workdir / "build.env")

        outcome = await pack.run_pack_build(
            image_ref=image_ref,
            source_path=source,
            log_path=log_file,
            env_file=env_file,
        )

    if outcome.succeeded:
        _append(log_file, f"\nBuilt {image_ref} in {outcome.duration_seconds:.0f}s\n")
        await _finish(db, deployment, status=DeploymentStatus.BUILT, image_ref=image_ref)
    else:
        await _finish(
            db, deployment, status=DeploymentStatus.FAILED,
            error=outcome.error or "The build failed. See the build log.",
        )


def _append(path: Path, text: str) -> None:
    """Append to the build log. Never raises — logging must not fail a build."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        logger.warning("Could not write build log %s", path)
