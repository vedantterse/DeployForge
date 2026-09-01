"""
Repository — a GitHub repo the user has connected to DeployForge.

Holds the Phase 1 detection result: the summary columns the UI reads, plus the
complete structured result in `detection_meta` so no evidence is lost.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.deployment import Deployment
    from app.models.environment import EnvironmentVariable
    from app.models.user import User


class DetectedType(str, enum.Enum):
    """How the repository should be built. Mirrors the detection module's
    result type, but is defined here so `detection/` stays dependency-free."""

    DOCKER = "docker"
    FRAMEWORK = "framework"
    UNKNOWN = "unknown"


class Repository(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "repositories"
    __table_args__ = (
        # A user connects any given repo once *per deploy path*, so a monorepo
        # can have its frontend and backend connected as separate targets.
        # NULLS NOT DISTINCT (PostgreSQL 15+) is required: without it two rows
        # with a NULL deploy_path — both meaning "the repository root" — would
        # not collide, and the same repo could be connected twice.
        UniqueConstraint(
            "user_id",
            "github_repo_id",
            "deploy_path",
            name="uq_repository_user_github_repo",
            postgresql_nulls_not_distinct=True,
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # GitHub's numeric id — stable across renames, unlike full_name.
    github_repo_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    clone_url: Mapped[str] = mapped_column(Text, nullable=False)

    # Which directory inside the repository is the deployable app. NULL means
    # the repository root. Set by the user after the scan, because a monorepo
    # with a Python backend and a TypeScript frontend has two valid answers and
    # only the user knows which one they meant.
    deploy_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # --- Detection results (null until the repo has been analyzed) ---
    detected_type: Mapped[DetectedType | None] = mapped_column(
        Enum(
            DetectedType,
            name="detected_type",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    detected_framework: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Full structured DetectionResult: compose flag, evidence, reason.
    detection_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="repositories")
    deployments: Mapped[list["Deployment"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    environment_variables: Mapped[list["EnvironmentVariable"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    @property
    def target_label(self) -> str:
        """Human label for what is deployed, e.g. "octocat/app (frontend/)"."""
        if not self.deploy_path:
            return self.full_name
        return f"{self.full_name} ({self.deploy_path}/)"

    def __repr__(self) -> str:
        return f"<Repository {self.target_label} detected_type={self.detected_type}>"
