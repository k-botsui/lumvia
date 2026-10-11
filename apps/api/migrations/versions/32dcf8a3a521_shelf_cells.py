"""Allow the unified Shelf interface to organize both videos and Cells."""

import sqlalchemy as sa
from alembic import op

revision = "32dcf8a3a521"
down_revision = "61f75b81aa20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "shelf_cells",
        sa.Column(
            "shelf_id", sa.String(36), sa.ForeignKey("shelves.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("cell_id", sa.String(36), sa.ForeignKey("cells.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade():
    op.drop_table("shelf_cells")
