"""add slack notification tracking

Revision ID: 20260322_0004
Revises: 20260322_0003
Create Date: 2026-03-22 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260322_0004"
down_revision: str | None = "20260322_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("slack_notified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_jobs_slack_notified", "jobs", ["slack_notified_at"])


def downgrade() -> None:
    op.drop_index("idx_jobs_slack_notified", table_name="jobs")
    op.drop_column("jobs", "slack_notified_at")
