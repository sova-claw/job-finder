"""create company snapshots

Revision ID: 20260322_0003
Revises: 20260309_0002
Create Date: 2026-03-22 10:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260322_0003"
down_revision = "20260309_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_snapshots",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("airtable_record_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("geo_bucket", sa.Text(), nullable=True),
        sa.Column("track_fit_sdet", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("track_fit_ai", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("brand_tier", sa.Text(), nullable=True),
        sa.Column("salary_hypothesis", sa.Text(), nullable=True),
        sa.Column("careers_url", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
        sa.UniqueConstraint("airtable_record_id"),
    )
    op.create_index("idx_company_snapshots_name", "company_snapshots", ["name"])
    op.create_index("idx_company_snapshots_country", "company_snapshots", ["country"])


def downgrade() -> None:
    op.drop_index("idx_company_snapshots_country", table_name="company_snapshots")
    op.drop_index("idx_company_snapshots_name", table_name="company_snapshots")
    op.drop_table("company_snapshots")
