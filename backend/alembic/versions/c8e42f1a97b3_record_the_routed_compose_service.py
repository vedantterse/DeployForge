"""Record which compose service is routed.

Revision ID: c8e42f1a97b3
Revises: b3d71c9a5e42

It was being recovered by looking for `-<service>-` inside the container name.
A compose file that sets its own `container_name:` leaves nothing in that name
to recover it from, so the routed service is stored instead of inferred.
"""

import sqlalchemy as sa
from alembic import op

revision = "c8e42f1a97b3"
down_revision = "b3d71c9a5e42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column("compose_web_service", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deployments", "compose_web_service")
