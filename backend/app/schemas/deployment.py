"""API shapes for deployments — what was analyzed, when, and by whom."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.deployment import BuildMethod, DeploymentStatus
from app.models.event import EventLevel
from app.models.repository import DetectedType
from app.models.user import UserRole


class DeploymentOut(BaseModel):
    """
    One deployment attempt, flattened with the repository it belongs to.

    The repository fields are denormalized into the response so a list view
    needs a single request rather than one lookup per row.
    """

    id: uuid.UUID
    status: DeploymentStatus
    build_method: BuildMethod | None = None
    commit_sha: str | None = None
    created_at: datetime
    updated_at: datetime

    # --- build ---
    image_ref: str | None = None
    build_started_at: datetime | None = None
    build_finished_at: datetime | None = None
    error_message: str | None = None
    has_logs: bool = False

    # --- runtime ---
    url: str | None = None
    subdomain: str | None = None
    app_port: int | None = None
    container_name: str | None = None
    runtime_started_at: datetime | None = None
    runtime_stopped_at: datetime | None = None
    suspended_by_admin: bool = False
    suspension_reason: str | None = None
    compose_project: str | None = None
    compose_services: list[str] | None = None
    compose_web_service: str | None = None

    repository_id: uuid.UUID
    full_name: str
    deploy_path: str | None = None
    target_label: str
    detected_type: DetectedType | None = None
    detected_framework: str | None = None

    # Populated on admin views only.
    user_id: uuid.UUID | None = None
    user_email: EmailStr | None = None


class UserDeploymentsOut(BaseModel):
    """A user together with their deployments — the admin overview."""

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    deployment_count: int
    repository_count: int
    running_count: int = 0
    max_deployments: int = 3
    can_deploy: bool = True
    deploy_block_reason: str | None = None
    github_username: str | None = None
    deployments: list[DeploymentOut]


class BuildStartedOut(BaseModel):
    """Acknowledgement that a build was queued. It runs in the background."""

    deployment_id: uuid.UUID
    status: DeploymentStatus
    target_label: str


class BuildLogsOut(BaseModel):
    """Build output so far. Polled while a build is running."""

    deployment_id: uuid.UUID
    status: DeploymentStatus
    logs: str
    truncated: bool = False


class DeploymentEventOut(BaseModel):
    """One line of a deployment's timeline."""

    id: uuid.UUID
    stage: str
    level: EventLevel
    message: str
    actor: str | None = None
    created_at: datetime


class RuntimeLogsOut(BaseModel):
    """What the running container has printed."""

    deployment_id: uuid.UUID
    status: DeploymentStatus
    logs: str
    running: bool = False


class AdminUserUpdate(BaseModel):
    """The fields an admin may change on an account."""

    is_active: bool | None = None
    max_deployments: int | None = Field(default=None, ge=0, le=50)
    role: UserRole | None = None
    # Revoking deploy rights is deliberately separate from disabling the
    # account: it stops the student adding load to the shared machine while
    # leaving them able to log in and see their history.
    can_deploy: bool | None = None
    deploy_block_reason: str | None = Field(default=None, max_length=500)


class SuspendRequest(BaseModel):
    """Why a deployment is being suspended, shown to its owner."""

    reason: str | None = Field(default=None, max_length=500)


class PlatformAnalyticsOut(BaseModel):
    """Everything the admin overview charts and counts."""

    users: int
    admins: int
    active_users: int
    blocked_users: int
    github_connections: int
    repositories: int
    deployments: int
    running: int
    stopped: int
    failed: int
    suspended: int
    # Build method mix, e.g. {"docker": 4, "buildpack": 2, "compose": 1}.
    by_method: dict[str, int] = {}
    by_framework: dict[str, int] = {}
    by_status: dict[str, int] = {}
    # Deployments created per day, oldest first: [{"date": "2026-09-01", "count": 3}]
    daily: list[dict] = []
    # Busiest accounts, most deployments first.
    top_users: list[dict] = []
    # Median and worst build durations, in seconds.
    build_seconds_median: float | None = None
    build_seconds_max: float | None = None
    success_rate: float | None = None


class PlatformStatusOut(BaseModel):
    """Whether the moving parts the platform depends on are up."""

    docker: bool
    registry: bool
    router: bool
    buildpacks: bool
    detail: dict[str, str] = {}
