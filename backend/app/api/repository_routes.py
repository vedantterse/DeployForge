"""
Connected-repository routes.

The flow is deliberately two-step:

    POST /repos/scan    download once, detect the root and every top-level
                        directory, return the candidates
    POST /repos/select  the user picks one; it is recorded and analyzed

The split exists because scanning cannot decide for the user. A monorepo with a
Python backend and a TypeScript frontend has two valid answers, and only the
person deploying knows which one they meant. `POST /repos/{id}/analyze`
re-runs detection later against the target they chose.

Downloads always live in a temporary directory that is removed when the request
finishes, and nothing from a repository is ever executed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.errors import AppError, NotFoundError
from app.db import get_db
from app.detection.candidates import (
    ROOT_PATH,
    RepositoryCandidate,
    deployable_candidates,
    resolve_path,
    scan_candidates,
)
from app.detection.detector import (
    DetectedType as DetectorType,
    DetectionResult,
    detect_repository,
)
from app.github import client as github_client
from app.github.download import downloaded_repository
from app.github.scan_token import create_scan_token, read_scan_token
from app.github.token import get_access_token
from app.models.deployment import BuildMethod, Deployment, DeploymentStatus
from app.models.repository import DetectedType, Repository
from app.schemas.repository import (
    CandidateOut,
    DetectionOut,
    RepositoryOut,
    ScanOut,
    ScanRepoRequest,
    SelectTargetRequest,
)

router = APIRouter(prefix="/repos", tags=["repositories"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


class UnknownTargetError(AppError):
    code = "unknown_target"
    status_code = 400


def _label_for(path: str) -> str:
    return "Whole repository" if path == ROOT_PATH else f"{path}/"


def _candidate_out(candidate: RepositoryCandidate) -> CandidateOut:
    result = candidate.result
    return CandidateOut(
        path=candidate.path,
        label=_label_for(candidate.path),
        type=DetectedType(result.type.value),
        framework=result.framework,
        compose=result.compose,
        build_method=BuildMethod(result.build_method) if result.build_method else None,
        evidence=result.evidence,
        reason=result.reason,
    )


async def _owned_repository(
    db: AsyncSession, repo_id: uuid.UUID, user_id: uuid.UUID
) -> Repository:
    """Load a repository, scoped to its owner so ids are not usable across users."""
    result = await db.execute(
        select(Repository).where(
            Repository.id == repo_id, Repository.user_id == user_id
        )
    )
    repository = result.scalar_one_or_none()
    if repository is None:
        raise NotFoundError("Repository not found.")
    return repository


async def _persist_detection(
    db: AsyncSession,
    repository: Repository,
    result: DetectionResult,
    commit_sha: str | None,
) -> Deployment:
    """
    Write a detection result to the database.

    The detector returns plain strings that already match the DB enums
    (`docker`/`framework`/`unknown`, `docker`/`buildpack`), so this is a value
    lookup rather than a translation. The complete result is also kept in
    `detection_meta` so nothing the detector found is lost.
    """
    repository.detected_type = DetectedType(result.type.value)
    repository.detected_framework = result.framework
    repository.detection_meta = result.to_dict()
    repository.last_analyzed_at = datetime.now(timezone.utc)

    # A repository being connected for the first time has no id until it is
    # flushed, and the Deployment below needs one.
    await db.flush()

    # One row per analysis: SCHEMA.md treats Deployment as "one record per
    # deployment attempt", so re-analyzing appends rather than overwrites.
    deployment = Deployment(
        repository_id=repository.id,
        user_id=repository.user_id,
        commit_sha=commit_sha,
        build_method=BuildMethod(result.build_method) if result.build_method else None,
        status=DeploymentStatus.ANALYZED,
    )
    db.add(deployment)

    await db.commit()
    await db.refresh(repository)
    await db.refresh(deployment)
    return deployment


def _detection_out(
    repository: Repository,
    deployment: Deployment,
    result: DetectionResult,
    commit_sha: str | None,
    file_count: int,
    total_bytes: int,
) -> DetectionOut:
    return DetectionOut(
        repository_id=repository.id,
        deployment_id=deployment.id,
        full_name=repository.full_name,
        deploy_path=repository.deploy_path,
        type=repository.detected_type,
        framework=result.framework,
        compose=result.compose,
        build_method=deployment.build_method,
        evidence=result.evidence,
        reason=result.reason,
        commit_sha=commit_sha,
        file_count=file_count,
        total_bytes=total_bytes,
        analyzed_at=repository.last_analyzed_at,
    )


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

@router.get("", response_model=list[RepositoryOut])
async def list_connected(current_user: CurrentUser, db: DbSession) -> list[RepositoryOut]:
    """Deploy targets this user has connected."""
    result = await db.execute(
        select(Repository)
        .where(Repository.user_id == current_user.id)
        .order_by(Repository.created_at.desc())
    )
    return [RepositoryOut.model_validate(r) for r in result.scalars().all()]


# ---------------------------------------------------------------------------
# Step 1 — scan
# ---------------------------------------------------------------------------

@router.post("/scan", response_model=ScanOut)
async def scan_repository(
    payload: ScanRepoRequest, current_user: CurrentUser, db: DbSession
) -> ScanOut:
    """
    Download a repository once and report every target it could deploy.

    Nothing is written to the database — the user has not chosen yet. The
    result comes back in a signed `scan_token` so the choice does not require
    downloading again.
    """
    access_token = await get_access_token(db, current_user.id)
    metadata = await github_client.get_repository(access_token, payload.full_name)
    branch = metadata["default_branch"]
    commit_sha = await github_client.get_head_commit(
        access_token, metadata["full_name"], branch
    )

    async with downloaded_repository(access_token, metadata["full_name"], branch) as download:
        candidates = deployable_candidates(scan_candidates(download.path))
        file_count, total_bytes = download.file_count, download.total_bytes

    scan_token = create_scan_token(
        current_user.id,
        {
            "metadata": metadata,
            "commit_sha": commit_sha,
            "file_count": file_count,
            "total_bytes": total_bytes,
            "candidates": [c.to_dict() for c in candidates],
        },
    )

    return ScanOut(
        full_name=metadata["full_name"],
        default_branch=branch,
        commit_sha=commit_sha,
        file_count=file_count,
        total_bytes=total_bytes,
        candidates=[_candidate_out(c) for c in candidates],
        scan_token=scan_token,
    )


# ---------------------------------------------------------------------------
# Step 2 — select a target
# ---------------------------------------------------------------------------

@router.post("/select", response_model=DetectionOut, status_code=status.HTTP_201_CREATED)
async def select_target(
    payload: SelectTargetRequest, current_user: CurrentUser, db: DbSession
) -> DetectionOut:
    """
    Record the target the user picked, with the detection result from the scan.

    Everything here comes from the signed scan token, never from the rest of
    the request body, so a client cannot claim a repository it has no access to
    or a detection result that never happened. Connecting the same repository
    at a different path creates a separate target.
    """
    claims = read_scan_token(payload.scan_token, current_user.id)
    metadata = claims["metadata"]

    deploy_path = payload.deploy_path.strip().strip("/")
    chosen = next(
        (c for c in claims["candidates"] if c["path"] == deploy_path), None
    )
    if chosen is None:
        raise UnknownTargetError(
            f"{_label_for(deploy_path)} was not one of the scanned targets."
        )

    stored_path = deploy_path or None  # NULL means the repository root

    existing = await db.execute(
        select(Repository).where(
            Repository.user_id == current_user.id,
            Repository.github_repo_id == metadata["github_repo_id"],
            Repository.deploy_path.is_(None)
            if stored_path is None
            else Repository.deploy_path == stored_path,
        )
    )
    repository = existing.scalar_one_or_none()
    if repository is None:
        repository = Repository(
            user_id=current_user.id,
            github_repo_id=metadata["github_repo_id"],
            deploy_path=stored_path,
        )
        db.add(repository)

    repository.name = metadata["name"]
    repository.full_name = metadata["full_name"]
    repository.default_branch = metadata["default_branch"]
    repository.clone_url = metadata["clone_url"]

    # Rebuild the detector's own result object from the signed scan, so the
    # same persistence path is used whether the result came from a scan or a
    # fresh analysis.
    result = DetectionResult(
        type=DetectorType(chosen["type"]),
        framework=chosen["framework"],
        compose=chosen["compose"],
        build_method=chosen["build_method"],
        evidence=list(chosen["evidence"]),
        reason=chosen["reason"],
    )
    deployment = await _persist_detection(db, repository, result, claims["commit_sha"])

    return _detection_out(
        repository,
        deployment,
        result,
        claims["commit_sha"],
        claims["file_count"],
        claims["total_bytes"],
    )


# ---------------------------------------------------------------------------
# Re-analysis
# ---------------------------------------------------------------------------

@router.post("/{repo_id}/analyze", response_model=DetectionOut)
async def analyze_repository(
    repo_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> DetectionOut:
    """
    Re-download the repository and detect the target the user chose.

    Docker configuration wins if present; otherwise the framework decides and
    the build method is a buildpack. The temp directory is deleted when the
    request finishes, whatever the outcome.
    """
    repository = await _owned_repository(db, repo_id, current_user.id)
    access_token = await get_access_token(db, current_user.id)

    commit_sha = await github_client.get_head_commit(
        access_token, repository.full_name, repository.default_branch
    )

    async with downloaded_repository(
        access_token, repository.full_name, repository.default_branch
    ) as download:
        try:
            target = resolve_path(download.path, repository.deploy_path or ROOT_PATH)
        except ValueError as exc:
            raise UnknownTargetError(str(exc)) from exc
        if not target.is_dir():
            raise NotFoundError(
                f"{_label_for(repository.deploy_path or ROOT_PATH)} no longer exists "
                f"in {repository.full_name}."
            )
        # Pure: reads and parses files, runs nothing.
        result = detect_repository(target)
        file_count, total_bytes = download.file_count, download.total_bytes

    deployment = await _persist_detection(db, repository, result, commit_sha)
    return _detection_out(
        repository, deployment, result, commit_sha, file_count, total_bytes
    )
