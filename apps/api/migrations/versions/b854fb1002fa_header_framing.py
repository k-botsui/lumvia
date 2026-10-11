"""Retain the chosen view of private shelf headers."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b854fb1002fa"
down_revision = "a174cf620fab"
branch_labels = None
depends_on = None


def upgrade():
    for table in ["shelves", "collections"]:
        op.add_column(
            table,
            sa.Column(
                "header_frame",
                postgresql.JSONB(),
                server_default=sa.text('\'{"x": 50, "y": 50, "zoom": 1}\'::jsonb'),
                nullable=False,
            ),
        )


def downgrade():
    for table in ["shelves", "collections"]:
        op.drop_column(table, "header_frame")
