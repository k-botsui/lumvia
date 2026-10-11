"""Private header images for shelves and legacy collections."""

import sqlalchemy as sa
from alembic import op

revision = "a174cf620fab"
down_revision = "32dcf8a3a521"
branch_labels = None
depends_on = None


def upgrade():
    for table in ["shelves", "collections"]:
        op.add_column(table, sa.Column("header_key", sa.String(length=500), nullable=True))


def downgrade():
    for table in ["shelves", "collections"]:
        op.drop_column(table, "header_key")
