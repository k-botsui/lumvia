"""Private reference people for bounded local scene search."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "61f75b81aa20"
down_revision = "ee7455b0f218"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "person_targets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "library_id", sa.String(36), sa.ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("embedding", postgresql.JSONB(), nullable=False),
        sa.Column("model_version", sa.String(200), nullable=False),
        sa.Column("image_key", sa.String(500), nullable=False, unique=True),
    )
    op.create_index("ix_person_targets_library_id", "person_targets", ["library_id"])


def downgrade():
    op.drop_table("person_targets")
