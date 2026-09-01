"""add deployment image_ref and build timestamps

Revision ID: 5ddac389328c
Revises: 4c94e21be0ed
Create Date: 2026-09-01 18:28:31.821041

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5ddac389328c'
down_revision: Union[str, None] = '4c94e21be0ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Record what a build produced, and add a status for "image built"."""
    # SCHEMA.md's enum went straight from `building` to `running`, leaving no
    # way to say "the image exists but nothing is started". PostgreSQL can add
    # an enum value in a transaction as long as the value is not used in the
    # same transaction, which it is not here.
    op.execute("ALTER TYPE deployment_status ADD VALUE IF NOT EXISTS 'built' AFTER 'building'")
    op.add_column('deployments', sa.Column('image_ref', sa.String(length=512), nullable=True))
    op.add_column('deployments', sa.Column('build_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('deployments', sa.Column('build_finished_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """
    Drop the build columns.

    The `built` enum value is deliberately left in place: PostgreSQL cannot
    remove one without recreating the type, and any row already using it would
    have to be rewritten first. An unused enum value is harmless.
    """
    op.drop_column('deployments', 'build_finished_at')
    op.drop_column('deployments', 'build_started_at')
    op.drop_column('deployments', 'image_ref')
