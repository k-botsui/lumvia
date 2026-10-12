"""Remember imported link lists to prevent duplicate Shelves."""

import sqlalchemy as sa
from alembic import op

revision = "fc62ea831412"
down_revision = "dac802c8e711"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "link_share_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "library_id", sa.String(36), sa.ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("summary", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("library_id", "fingerprint"),
    )


def downgrade():
    op.drop_table("link_share_imports")
