"""
GitHubConnection — DeployForge's authorized access to a user's GitHub account.

This is deliberately NOT login. The user logs into DeployForge first (see
`User`), then grants this connection over OAuth. One row per user: the unique
constraint on `user_id` is what makes the relationship one-to-one.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class GitHubConnection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "github_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one connection per user
    )
    github_username: Mapped[str] = mapped_column(String(255), nullable=False)
    github_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # The OAuth token, Fernet-encrypted. The plaintext token is never stored.
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship(back_populates="github_connection")

    def __repr__(self) -> str:
        return f"<GitHubConnection github_username={self.github_username}>"
