"""add job slack channel metadata

Revision ID: 20260323_0007
Revises: 20260323_0006
Create Date: 2026-03-23 13:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260323_0007"
down_revision: str | None = "20260323_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("slack_channel_id", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("slack_channel_name", sa.Text(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("slack_channel_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_jobs_slack_channel_id", "jobs", ["slack_channel_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_jobs_slack_channel_id", table_name="jobs")
    op.drop_column("jobs", "slack_channel_created_at")
    op.drop_column("jobs", "slack_channel_name")
    op.drop_column("jobs", "slack_channel_id")
