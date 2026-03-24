"""add plan task slack thread tracking

Revision ID: 20260324_0009
Revises: 20260324_0008
Create Date: 2026-03-24 13:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260324_0009"
down_revision: str | None = "20260324_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plan_tasks", sa.Column("slack_thread_ts", sa.Text(), nullable=True))
    op.add_column("plan_tasks", sa.Column("slack_last_post_ts", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("plan_tasks", "slack_last_post_ts")
    op.drop_column("plan_tasks", "slack_thread_ts")
