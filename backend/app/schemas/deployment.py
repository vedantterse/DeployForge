"""API shapes for deployments — what was analyzed, when, and by whom."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.deployment import BuildMethod, DeploymentStatus
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
    github_username: str | None = None
    deployments: list[DeploymentOut]
