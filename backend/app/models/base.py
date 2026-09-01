"""
SQLAlchemy declarative base and shared column mixins.

Every table in DeployForge has a UUID primary key and created_at/updated_at
timestamps (see SCHEMA.md), so those live here as mixins rather than being
repeated on each model.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base; `Base.metadata` is what Alembic autogenerates from."""


class UUIDMixin:
    """UUID primary key, generated application-side so it is known before flush."""

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-100,  # keep `id` the first column on every table
    )


class TimestampMixin:
    """created_at / updated_at, both maintained by the database clock."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        sort_order=101,
    )
