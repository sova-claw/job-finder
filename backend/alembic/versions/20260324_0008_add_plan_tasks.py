"""add plan tasks

Revision ID: 20260324_0008
Revises: 20260323_0007
Create Date: 2026-03-24 12:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260324_0008"
down_revision: str | None = "20260323_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_tasks",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("story_points", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("next_step", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_plan_tasks_title", "plan_tasks", ["title"])
    op.create_index("idx_plan_tasks_status", "plan_tasks", ["status"])
    op.create_index("idx_plan_tasks_created_at", "plan_tasks", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_plan_tasks_created_at", table_name="plan_tasks")
    op.drop_index("idx_plan_tasks_status", table_name="plan_tasks")
    op.drop_index("idx_plan_tasks_title", table_name="plan_tasks")
    op.drop_table("plan_tasks")
