"""add repository deploy_path

Revision ID: 14a29cd4dc98
Revises: a7aad1185ffc
Create Date: 2026-09-01 12:32:42.179339

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '14a29cd4dc98'
down_revision: Union[str, None] = 'a7aad1185ffc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add deploy_path and widen the uniqueness rule to include it.

    NULLS NOT DISTINCT (PostgreSQL 15+) makes two NULL deploy_paths collide, so
    "the repository root" can still only be connected once per user.
    """
    op.add_column('repositories', sa.Column('deploy_path', sa.String(length=512), nullable=True))
    op.drop_constraint('uq_repository_user_github_repo', 'repositories', type_='unique')
    op.create_unique_constraint('uq_repository_user_github_repo', 'repositories', ['user_id', 'github_repo_id', 'deploy_path'], postgresql_nulls_not_distinct=True)


def downgrade() -> None:
    """Drop deploy_path. Rows differing only by deploy_path would now collide,
    so any extra targets must be removed before downgrading."""
    op.drop_constraint('uq_repository_user_github_repo', 'repositories', type_='unique')
    op.create_unique_constraint('uq_repository_user_github_repo', 'repositories', ['user_id', 'github_repo_id'])
    op.drop_column('repositories', 'deploy_path')
