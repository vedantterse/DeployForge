"""create users, github_connections, repositories, deployments

Revision ID: a7aad1185ffc
Revises: 
Create Date: 2026-08-29 19:04:32.962106

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a7aad1185ffc'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the four Phase 1 tables (see SCHEMA.md)."""
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('admin', 'user', name='user_role'), server_default='user', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('github_connections',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('github_username', sa.String(length=255), nullable=False),
    sa.Column('github_user_id', sa.BigInteger(), nullable=False),
    sa.Column('access_token_enc', sa.Text(), nullable=False),
    sa.Column('scopes', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('repositories',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('github_repo_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=512), nullable=False),
    sa.Column('default_branch', sa.String(length=255), nullable=False),
    sa.Column('clone_url', sa.Text(), nullable=False),
    sa.Column('detected_type', sa.Enum('docker', 'framework', 'unknown', name='detected_type'), nullable=True),
    sa.Column('detected_framework', sa.String(length=64), nullable=True),
    sa.Column('detection_meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('last_analyzed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'github_repo_id', name='uq_repository_user_github_repo')
    )
    op.create_index(op.f('ix_repositories_user_id'), 'repositories', ['user_id'], unique=False)
    op.create_table('deployments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('repository_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('commit_sha', sa.String(length=40), nullable=True),
    sa.Column('build_method', sa.Enum('docker', 'buildpack', name='build_method'), nullable=True),
    sa.Column('status', sa.Enum('analyzed', 'queued', 'building', 'running', 'live', 'failed', name='deployment_status'), server_default='analyzed', nullable=False),
    sa.Column('subdomain', sa.String(length=255), nullable=True),
    sa.Column('container_id', sa.String(length=128), nullable=True),
    sa.Column('target_server_ip', sa.String(length=45), nullable=True),
    sa.Column('logs_ref', sa.Text(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_deployments_repository_id'), 'deployments', ['repository_id'], unique=False)
    op.create_index(op.f('ix_deployments_status'), 'deployments', ['status'], unique=False)
    op.create_index(op.f('ix_deployments_user_id'), 'deployments', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop the tables, then the enum types they created."""
    op.drop_index(op.f('ix_deployments_user_id'), table_name='deployments')
    op.drop_index(op.f('ix_deployments_status'), table_name='deployments')
    op.drop_index(op.f('ix_deployments_repository_id'), table_name='deployments')
    op.drop_table('deployments')
    op.drop_index(op.f('ix_repositories_user_id'), table_name='repositories')
    op.drop_table('repositories')
    op.drop_table('github_connections')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    # Dropping a table does not drop the PostgreSQL enum types created with it;
    # without this, re-running the upgrade fails with "type already exists".
    for enum_name in ("deployment_status", "build_method", "detected_type", "user_role"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
