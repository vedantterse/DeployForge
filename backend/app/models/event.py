"""
DeploymentEvent — the timeline of what happened to a deployment.

`Deployment.status` says where a deployment is now; this table says how it got
there. Without it a failed deployment is a single red word, and neither the
student nor the admin can tell whether it died in the download, the build, the
push or the first second of runtime.

Events are append-only and deliberately cheap to write, so every step of the
pipeline can record one without worrying about cost.
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
    from app.models.deployment import Deployment


class EventLevel(str, enum.Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class DeploymentEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "deployment_events"

    deployment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("deployments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # A short machine-readable step name: "download", "build", "push", "start".
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[EventLevel] = mapped_column(
        Enum(
            EventLevel,
            name="event_level",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=EventLevel.INFO,
        server_default=EventLevel.INFO.value,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Who caused it, when it was not the pipeline itself: "owner" or "admin".
    actor: Mapped[str | None] = mapped_column(String(32), nullable=True)

    deployment: Mapped["Deployment"] = relationship(back_populates="events")

    def __repr__(self) -> str:
        return f"<DeploymentEvent {self.stage} {self.level.value}>"
