"""
Orchestrate a build: download the repository, produce an image, store it.

The steps are the same ones the analysis flow uses — download to a temp
directory, resolve the chosen target — with the build in the middle and the
outcome written to the Deployment row.

Two build paths, chosen by what is actually in the directory being built:

  * a Dockerfile        -> `docker build`, because the student already said
                           exactly how their app should be assembled and
                           second-guessing that is never an improvement;
  * anything else       -> Cloud Native Buildpacks, which infer it.

The result is pushed to the registry. A locally-tagged image is a side effect
of the machine it was built on; an image in a registry is an artifact that can
be pulled, run elsewhere, and rolled back to.

This runs in the background, outside the HTTP request, so it opens its own
database session and never lets an exception escape: a crashed build must leave
the deployment marked `failed` with a reason, not stuck in `building` forever.
"""

from __future__ import annotations

import logging
import tempfile
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
from app.detection.detector import _COMPOSE_NAMES, _DOCKERFILE_NAMES
from app.github import client as github_client
from app.github.download import downloaded_repository
from app.github.token import get_access_token
from app.models.deployment import BuildMethod, Deployment, DeploymentStatus
from app.models.environment import EnvironmentVariable
from app.models.event import EventLevel
from app.models.repository import Repository
from app.runtime import docker
from app.runtime.service import record

logger = logging.getLogger(__name__)


def log_path_for(deployment_id: uuid.UUID) -> Path:
    """
    Where a deployment's build log lives.

    The fallback is the platform temp directory rather than a literal "/tmp":
    on Windows that path is not the temp directory and resolves to `C:\\tmp`
    on whichever drive is current.
    """
    base = settings.build_log_dir.strip() or settings.repo_workdir.strip()
    root = Path(base) if base else Path(tempfile.gettempdir())
    directory = root / "deployforge-build-logs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{deployment_id}.log"


def find_dockerfile(source: Path) -> Path | None:
    """The Dockerfile in this directory, if there is one."""
    for name in _DOCKERFILE_NAMES:
        candidate = source / name
        if candidate.is_file():
            return candidate
    return None


def has_compose(source: Path) -> bool:
    """Whether this directory defines a multi-service compose stack."""
    return any((source / name).is_file() for name in _COMPOSE_NAMES)


def registry_ref(local_ref: str) -> str:
    """
    The image's name in the registry.

    Returns the local tag unchanged when pushing is disabled, so a machine
    without a registry still produces a runnable image.
    """
    return f"{settings.registry_prefix}{local_ref}"


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
        await record(
            db, deployment_id, "build",
            f"Build failed: {type(exc).__name__}: {exc}",
            level=EventLevel.ERROR,
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

    local_ref = pack.build_image_ref(
        user_id=repository.user_id,
        repository_name=repository.name,
        deploy_path=repository.deploy_path,
        commit_sha=commit_sha,
    )
    image_ref = registry_ref(local_ref)
    env = await _environment_for(db, repository.id)

    await record(
        db, deployment.id, "download",
        f"Downloading {repository.full_name} at {repository.default_branch}.",
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

        # The directory being built is the authority on how to build it — not
        # the detection row, which may predate a commit that added a Dockerfile.
        dockerfile = find_dockerfile(source)
        method = BuildMethod.DOCKER if dockerfile else BuildMethod.BUILDPACK
        deployment.build_method = method
        await db.commit()

        _append(
            log_file,
            f"Building {repository.target_label}\n"
            f"  branch     {repository.default_branch}\n"
            f"  commit     {commit_sha or 'unknown'}\n"
            f"  image      {image_ref}\n"
            f"  method     {method.value}\n"
            f"  env vars   {len(env)}\n\n",
        )
        await record(
            db, deployment.id, "build",
            f"Building with {'the repository Dockerfile' if dockerfile else 'Cloud Native Buildpacks'}.",
        )

        if has_compose(source) and dockerfile is None:
            # Compose describes several services and their wiring; there is no
            # single image to produce, so say that plainly instead of building
            # something that is not what the file describes.
            await _finish(
                db, deployment, status=DeploymentStatus.FAILED,
                error=(
                    "This target uses Docker Compose, which describes multiple "
                    "services. DeployForge runs one image per deployment — add a "
                    "Dockerfile for the service you want to deploy, or pick a "
                    "subdirectory that has one."
                ),
            )
            return

        if dockerfile is not None:
            succeeded, error = await _build_with_docker(
                image_ref=image_ref, source=source,
                dockerfile=dockerfile, log_file=log_file,
            )
        else:
            succeeded, error = await _build_with_buildpacks(
                image_ref=image_ref, source=source,
                workdir=download.workdir, env=env, log_file=log_file,
            )

    if not succeeded:
        await _finish(
            db, deployment, status=DeploymentStatus.FAILED,
            error=error or "The build failed. See the build log.",
        )
        await record(
            db, deployment.id, "build",
            error or "The build failed.", level=EventLevel.ERROR,
        )
        return

    await record(
        db, deployment.id, "build", f"Built {image_ref}.", level=EventLevel.SUCCESS
    )
    await _push(db, deployment, image_ref, log_file)

    await _finish(db, deployment, status=DeploymentStatus.BUILT, image_ref=image_ref)


async def _build_with_docker(
    *, image_ref: str, source: Path, dockerfile: Path, log_file: Path
) -> tuple[bool, str | None]:
    """Build the student's own Dockerfile."""
    result = await docker.build_image(
        image_ref=image_ref,
        context_path=source,
        dockerfile=dockerfile,
        log_path=log_file,
    )
    if result.ok:
        _append(log_file, f"\nBuilt {image_ref} from {dockerfile.name}.\n")
        return True, None
    return False, f"docker build failed: {result.message}"


async def _build_with_buildpacks(
    *, image_ref: str, source: Path, workdir: Path,
    env: dict[str, str], log_file: Path,
) -> tuple[bool, str | None]:
    """Build with Cloud Native Buildpacks, which infer the whole recipe."""
    await pack.check_toolchain()

    # The env file lives inside the temp workdir, which is deleted with it.
    env_file = pack.write_env_file(env, workdir / "build.env") if env else None

    outcome = await pack.run_pack_build(
        image_ref=image_ref,
        source_path=source,
        log_path=log_file,
        env_file=env_file,
    )
    if outcome.succeeded:
        _append(
            log_file,
            f"\nBuilt {image_ref} in {outcome.duration_seconds:.0f}s.\n",
        )
        return True, None
    return False, outcome.error or "The buildpack build failed."


async def _push(
    db: AsyncSession, deployment: Deployment, image_ref: str, log_file: Path
) -> None:
    """
    Store the image in the registry.

    A push failure is recorded but does not fail the build: the image exists
    locally and this deployment runs on the same host, so the app still works.
    Losing the *artifact* is worth a warning, not a red deployment.
    """
    if not settings.registry_push:
        return

    deployment.status = DeploymentStatus.PUSHING
    await db.commit()

    _append(log_file, f"\nPushing {image_ref} to the registry...\n")
    result = await docker.push_image(image_ref, log_path=log_file)

    if result.ok:
        await record(
            db, deployment.id, "push",
            f"Pushed {image_ref} to the registry.", level=EventLevel.SUCCESS,
        )
    else:
        _append(log_file, f"\nPush failed: {result.message}\n")
        await record(
            db, deployment.id, "push",
            f"Could not push to the registry ({result.message}). The image is "
            "available locally, so the app can still run.",
            level=EventLevel.WARNING,
        )


def _append(path: Path, text: str) -> None:
    """Append to the build log. Never raises — logging must not fail a build."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        logger.warning("Could not write build log %s", path)
