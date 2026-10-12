"""Record submission receipts without saving contact message contents."""

import sqlalchemy as sa
from alembic import op

revision = "dac802c8e711"
down_revision = "b854fb1002fa"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "support_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("issue_url", sa.String(300)),
        sa.Column("issue_number", sa.Integer()),
        sa.UniqueConstraint("user_id", "request_id"),
    )


def downgrade():
    op.drop_table("support_submissions")
