"""
EnvironmentVariable — configuration supplied to a deploy target at build time.

Values are Fernet-encrypted at rest *whether or not* they are marked secret:
encryption is about what sits in the database, while `is_secret` only controls
whether the plaintext is ever sent back to the browser.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.repository import Repository


class EnvironmentVariable(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "environment_variables"
    __table_args__ = (
        UniqueConstraint("repository_id", "key", name="uq_env_var_repository_key"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    value_enc: Mapped[str] = mapped_column(Text, nullable=False)
    # When true the plaintext is never returned by the API — the UI shows a mask.
    is_secret: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    repository: Mapped["Repository"] = relationship(back_populates="environment_variables")

    def __repr__(self) -> str:
        return f"<EnvironmentVariable {self.key} secret={self.is_secret}>"
