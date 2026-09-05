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

    # Fetch server-generated values (created_at, and updated_at's `onupdate`)
    # during the flush itself, via PostgreSQL's RETURNING.
    #
    # Without this they are left *expired* after an INSERT or UPDATE, so the
    # next read of `updated_at` silently emits a SELECT. Under asyncio that
    # read happens outside a greenlet context — building a response object is
    # ordinary synchronous attribute access — and raises MissingGreenlet
    # instead of loading. Fetching eagerly means the values are simply there.
    __mapper_args__ = {"eager_defaults": True}


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
