"""
Deployment — one deployment attempt for a Repository.

Created now, mostly populated later. Phase 1 writes a row at analysis time with
status `analyzed` and the `build_method` detection chose; every infrastructure
column stays null until the build/run/route phases fill it in. Keeping the
table from the start is what makes "the whole platform is reconstructable from
the database" true.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.user import User


class BuildMethod(str, enum.Enum):
    DOCKER = "docker"
    BUILDPACK = "buildpack"


class DeploymentStatus(str, enum.Enum):
    ANALYZED = "analyzed"
    QUEUED = "queued"
    BUILDING = "building"
    RUNNING = "running"
    LIVE = "live"
    FAILED = "failed"


class Deployment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployments"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized from Repository so "all deployments for a user" is one query.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    build_method: Mapped[BuildMethod | None] = mapped_column(
        Enum(
            BuildMethod,
            name="build_method",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(
            DeploymentStatus,
            name="deployment_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=DeploymentStatus.ANALYZED,
        server_default=DeploymentStatus.ANALYZED.value,
        index=True,
    )

    # --- Infrastructure columns: null in Phase 1, filled by later phases ---
    subdomain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_server_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    logs_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="deployments")
    user: Mapped["User"] = relationship(back_populates="deployments")

    def __repr__(self) -> str:
        return f"<Deployment {self.id} status={self.status.value}>"
