"""API shapes for connected repositories and their analysis."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.deployment import BuildMethod
from app.models.repository import DetectedType


class ScanRepoRequest(BaseModel):
    """Download a repository and see what could be deployed from it."""

    full_name: str = Field(min_length=3, max_length=512)


class CandidateOut(BaseModel):
    """One deployable target found in the repository."""

    path: str  # "" means the repository root
    label: str  # "Whole repository" or "frontend/"
    type: DetectedType
    framework: str | None = None
    compose: bool = False
    build_method: BuildMethod | None = None
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None
    # True when this exact target is already connected by this account. The
    # picker greys it out instead of letting the user choose it and hit a
    # unique-constraint error on the next request.
    already_connected: bool = False
    deployment_id: uuid.UUID | None = None
    # What actually became of it, so the picker can say "Failed" rather than
    # claiming a target is deployed when its build never finished.
    deployment_status: str | None = None


class ScanOut(BaseModel):
    """
    The result of scanning a repository: what is here, and what to send back.

    `scan_token` is a short-lived signed token holding the scan result. Posting
    it to /repos/select records the chosen target without downloading again,
    and because it is signed, the client cannot alter what was detected.
    """

    full_name: str
    default_branch: str
    commit_sha: str | None = None
    file_count: int
    total_bytes: int
    candidates: list[CandidateOut]
    scan_token: str


class SelectTargetRequest(BaseModel):
    """
    Choose what to connect from a scan.

    One `deploy_path` connects a single directory. Several `deploy_paths`
    connect them as one deployment running together on a private network —
    a frontend and the backend it calls are one app, not two.
    """

    scan_token: str
    deploy_path: str = Field(default="", max_length=512)
    deploy_paths: list[str] = Field(default_factory=list, max_length=10)

    @property
    def selected(self) -> list[str]:
        """The chosen directories, normalized and de-duplicated in order."""
        raw = self.deploy_paths or [self.deploy_path]
        seen: list[str] = []
        for path in raw:
            cleaned = path.strip().strip("/")
            if cleaned not in seen:
                seen.append(cleaned)
        return seen


class RepositoryOut(BaseModel):
    """A repository DeployForge has connected, with any detection result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    github_repo_id: int
    name: str
    full_name: str
    default_branch: str
    clone_url: str
    deploy_path: str | None = None
    service_paths: list[str] | None = None
    detected_type: DetectedType | None = None
    detected_framework: str | None = None
    detection_meta: dict[str, Any] | None = None
    last_analyzed_at: datetime | None = None
    created_at: datetime


class DetectionOut(BaseModel):
    """
    The result of analyzing a repository.

    Mirrors the pure detector's DetectionResult, plus the ids of the rows it
    was written to. By the time this is returned the downloaded files are gone.
    """

    repository_id: uuid.UUID
    deployment_id: uuid.UUID
    full_name: str
    deploy_path: str | None = None

    # --- detection ---
    type: DetectedType
    framework: str | None = None
    compose: bool = False
    build_method: BuildMethod | None = None
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None

    # --- context ---
    commit_sha: str | None = None
    file_count: int
    total_bytes: int
    analyzed_at: datetime
