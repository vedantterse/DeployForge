"""
SQLAlchemy models.

Importing this package imports every model, which registers all four tables on
`Base.metadata` — that is what Alembic autogenerate reads.
"""

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.deployment import BuildMethod, Deployment, DeploymentStatus
from app.models.github import GitHubConnection
from app.models.repository import DetectedType, Repository
from app.models.user import User, UserRole

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "User",
    "UserRole",
    "GitHubConnection",
    "Repository",
    "DetectedType",
    "Deployment",
    "BuildMethod",
    "DeploymentStatus",
]
