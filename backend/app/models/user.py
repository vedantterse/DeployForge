"""
User — who can log into DeployForge.

Admins manage the platform, users deploy apps. It is one auth system
differentiated by `role`, not two separate systems.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.deployment import Deployment
    from app.models.github import GitHubConnection
    from app.models.repository import Repository


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )
    # Soft-disable an account without deleting it or its history.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # How many apps this account may have running at once. The platform runs on
    # one machine shared by a whole class, so "deploy" has to be a bounded
    # privilege rather than an unlimited one. Admins raise it per student.
    max_deployments: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )

    github_connection: Mapped["GitHubConnection | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    repositories: Mapped[list["Repository"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    deployments: Mapped[list["Deployment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role.value}>"
