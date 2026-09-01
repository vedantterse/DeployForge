"""add environment_variables

Revision ID: 4c94e21be0ed
Revises: 14a29cd4dc98
Create Date: 2026-09-01 18:15:40.986499

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4c94e21be0ed'
down_revision: Union[str, None] = '14a29cd4dc98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Per-target environment variables, values encrypted at rest."""
    op.create_table('environment_variables',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('repository_id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=256), nullable=False),
    sa.Column('value_enc', sa.Text(), nullable=False),
    sa.Column('is_secret', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('repository_id', 'key', name='uq_env_var_repository_key')
    )
    op.create_index(op.f('ix_environment_variables_repository_id'), 'environment_variables', ['repository_id'], unique=False)


def downgrade() -> None:
    """Drop the table. Stored variable values are lost with it."""
    op.drop_index(op.f('ix_environment_variables_repository_id'), table_name='environment_variables')
    op.drop_table('environment_variables')
