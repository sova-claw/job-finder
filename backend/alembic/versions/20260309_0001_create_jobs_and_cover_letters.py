"""create jobs and cover_letters tables

Revision ID: 20260309_0001
Revises:
Create Date: 2026-03-09 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260309_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_group", sa.Text(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("company_type", sa.Text(), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("requirements_must", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("requirements_nice", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("remote", sa.Boolean(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_index("idx_jobs_score", "jobs", [sa.text("match_score DESC")])
    op.create_index("idx_jobs_salary", "jobs", [sa.text("salary_max DESC NULLS LAST")])
    op.create_index("idx_jobs_scraped", "jobs", [sa.text("scraped_at DESC")])
    op.create_index("idx_jobs_source", "jobs", ["source_group"])
    op.create_index("idx_jobs_search", "jobs", ["search_vector"], postgresql_using="gin")
    op.create_index("idx_jobs_tags", "jobs", ["tags"], postgresql_using="gin")

    op.create_table(
        "cover_letters",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "job_id",
            sa.Text(),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tone", sa.Text(), nullable=False),
        sa.Column("profile_hash", sa.Text(), nullable=False),
        sa.Column("letter", sa.Text(), nullable=False),
        sa.Column("tags_used", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_cl_unique",
        "cover_letters",
        ["job_id", "tone", "profile_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_cl_unique", table_name="cover_letters")
    op.drop_table("cover_letters")

    op.drop_index("idx_jobs_tags", table_name="jobs")
    op.drop_index("idx_jobs_search", table_name="jobs")
    op.drop_index("idx_jobs_source", table_name="jobs")
    op.drop_index("idx_jobs_scraped", table_name="jobs")
    op.drop_index("idx_jobs_salary", table_name="jobs")
    op.drop_index("idx_jobs_score", table_name="jobs")
    op.drop_table("jobs")
