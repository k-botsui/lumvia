"""External platform references, independent of managed assets.

Revision ID: ee7455b0f218
Revises: c83a0e996edd
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "ee7455b0f218"
down_revision = "c83a0e996edd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("external_url", sa.String(2048), nullable=True))
    op.add_column("sources", sa.Column("external_id", sa.String(100), nullable=True))
    op.add_column(
        "sources",
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_unique_constraint("uq_source_external", "sources", ["library_id", "kind", "external_id"])


def downgrade():
    op.drop_constraint("uq_source_external", "sources", type_="unique")
    op.drop_column("sources", "metadata_json")
    op.drop_column("sources", "external_id")
    op.drop_column("sources", "external_url")
