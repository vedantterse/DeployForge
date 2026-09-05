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

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.event import DeploymentEvent
    from app.models.repository import Repository
    from app.models.user import User


class BuildMethod(str, enum.Enum):
    DOCKER = "docker"
    BUILDPACK = "buildpack"


class DeploymentStatus(str, enum.Enum):
    ANALYZED = "analyzed"
    QUEUED = "queued"
    BUILDING = "building"
    # The image is being pushed to the registry after a successful build.
    PUSHING = "pushing"
    # The image exists but nothing is running yet. SCHEMA.md's original enum
    # went straight from `building` to `running`, which left no way to say
    # "built successfully, not yet started".
    BUILT = "built"
    # The container has been created and is being health-checked.
    STARTING = "starting"
    RUNNING = "running"
    LIVE = "live"
    # Ran successfully and was deliberately stopped — by the owner or an admin.
    STOPPED = "stopped"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """No background work is in flight; the user decides what happens next."""
        return self in {
            DeploymentStatus.BUILT,
            DeploymentStatus.LIVE,
            DeploymentStatus.RUNNING,
            DeploymentStatus.STOPPED,
            DeploymentStatus.FAILED,
        }

    @property
    def is_busy(self) -> bool:
        """A background task owns this deployment; refuse to start another."""
        return self in {
            DeploymentStatus.QUEUED,
            DeploymentStatus.BUILDING,
            DeploymentStatus.PUSHING,
            DeploymentStatus.STARTING,
        }

    @property
    def is_running(self) -> bool:
        return self in {DeploymentStatus.RUNNING, DeploymentStatus.LIVE}


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

    # --- Build output ---
    # The image the build produced, e.g.
    # "deployforge/a1b2c3-amvex-backend:3bb876b". A local Docker tag today; the
    # same column holds a full registry reference once one is introduced.
    image_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    build_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    build_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Runtime ---
    # The host label the app answers on, e.g. "todo-a1b2c3d4" reachable at
    # todo-a1b2c3d4.localhost. Unique platform-wide: it is a routing key.
    subdomain: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    container_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # The port the app listens on *inside* its container. Read from the image's
    # EXPOSE, else inferred from the framework, else a default.
    app_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runtime_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    runtime_stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when an admin stopped it, so the owner cannot simply start it again.
    suspended_by_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    target_server_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    logs_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="deployments")
    user: Mapped["User"] = relationship(back_populates="deployments")
    events: Mapped[list["DeploymentEvent"]] = relationship(
        back_populates="deployment",
        cascade="all, delete-orphan",
        order_by="DeploymentEvent.created_at",
    )

    @property
    def url(self) -> str | None:
        """Where the app answers, once it has a subdomain."""
        from app.config import settings

        if not self.subdomain:
            return None
        return f"http://{self.subdomain}.{settings.app_domain}"

    def __repr__(self) -> str:
        return f"<Deployment {self.id} status={self.status.value}>"
