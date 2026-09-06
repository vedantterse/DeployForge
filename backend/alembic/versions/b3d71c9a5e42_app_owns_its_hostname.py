"""The hostname belongs to the app, and is unique among live deployments.

Revision ID: b3d71c9a5e42
Revises: 068ad808b96f

`deployments.subdomain` used to be derived from the deployment, so a redeploy
handed the student a different URL for the same app and a plain UNIQUE index
was the right rule. It is now derived from the repository: every deployment of
one app shares the name, and the outright UNIQUE index would reject an app's
second build.

What must actually hold is that two deployments are never live at the same
address. A partial unique index says exactly that, and leaves the router with
one answer for every host it is asked about.

Existing rows keep their old per-deployment subdomains; they are recomputed
the next time each app is started.
"""

import sqlalchemy as sa
from alembic import op

revision = "b3d71c9a5e42"
down_revision = "068ad808b96f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLAlchemy created this as UNIQUE; the replacement is narrower.
    op.drop_index("ix_deployments_subdomain", table_name="deployments")
    op.create_index("ix_deployments_subdomain", "deployments", ["subdomain"])
    op.create_index(
        "uq_deployments_live_subdomain",
        "deployments",
        ["subdomain"],
        unique=True,
        postgresql_where=sa.text("status IN ('running', 'live')"),
    )


def downgrade() -> None:
    op.drop_index("uq_deployments_live_subdomain", table_name="deployments")
    op.drop_index("ix_deployments_subdomain", table_name="deployments")
    op.create_index(
        "ix_deployments_subdomain", "deployments", ["subdomain"], unique=True
    )
