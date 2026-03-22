"""add job scoring metadata

Revision ID: 20260323_0005
Revises: 20260322_0004
Create Date: 2026-03-23 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260323_0005"
down_revision: str | None = "20260322_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("hard_matches", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("soft_matches", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("jobs", sa.Column("dealbreaker", sa.Boolean(), nullable=True))
    op.add_column("jobs", sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_jobs_scored_at", "jobs", ["scored_at"])


def downgrade() -> None:
    op.drop_index("idx_jobs_scored_at", table_name="jobs")
    op.drop_column("jobs", "scored_at")
    op.drop_column("jobs", "dealbreaker")
    op.drop_column("jobs", "soft_matches")
    op.drop_column("jobs", "hard_matches")
