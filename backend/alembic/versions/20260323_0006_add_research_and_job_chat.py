"""add research findings and job chat

Revision ID: 20260323_0006
Revises: 20260323_0005
Create Date: 2026-03-23 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260323_0006"
down_revision: str | None = "20260323_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_chat_messages",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_job_chat_messages_job_id", "job_chat_messages", ["job_id"])
    op.create_index("idx_job_chat_messages_created_at", "job_chat_messages", ["created_at"])

    op.create_table(
        "research_findings",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=True),
        sa.Column("company_snapshot_id", sa.Text(), nullable=True),
        sa.Column("finding_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_kind", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["company_snapshot_id"],
            ["company_snapshots.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_findings_job_id", "research_findings", ["job_id"])
    op.create_index(
        "idx_research_findings_company_snapshot_id",
        "research_findings",
        ["company_snapshot_id"],
    )
    op.create_index("idx_research_findings_finding_type", "research_findings", ["finding_type"])
    op.create_index("idx_research_findings_created_at", "research_findings", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_research_findings_created_at", table_name="research_findings")
    op.drop_index("idx_research_findings_finding_type", table_name="research_findings")
    op.drop_index("idx_research_findings_company_snapshot_id", table_name="research_findings")
    op.drop_index("idx_research_findings_job_id", table_name="research_findings")
    op.drop_table("research_findings")

    op.drop_index("idx_job_chat_messages_created_at", table_name="job_chat_messages")
    op.drop_index("idx_job_chat_messages_job_id", table_name="job_chat_messages")
    op.drop_table("job_chat_messages")
