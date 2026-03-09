"""add search_vector trigger

Revision ID: 20260309_0002
Revises: 20260309_0001
Create Date: 2026-03-09 00:30:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260309_0002"
down_revision: str | None = "20260309_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION jobs_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
          NEW.search_vector :=
            to_tsvector(
              'english',
              concat_ws(
                ' ',
                coalesce(NEW.title, ''),
                coalesce(NEW.company, ''),
                coalesce(NEW.raw_text, ''),
                coalesce(NEW.domain, '')
              )
            );
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER jobs_search_vector_trigger
        BEFORE INSERT OR UPDATE OF title, company, raw_text, domain
        ON jobs
        FOR EACH ROW
        EXECUTE FUNCTION jobs_search_vector_update();
        """
    )
    op.execute(
        """
        UPDATE jobs
        SET search_vector = to_tsvector(
          'english',
          concat_ws(
            ' ',
            coalesce(title, ''),
            coalesce(company, ''),
            coalesce(raw_text, ''),
            coalesce(domain, '')
          )
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS jobs_search_vector_trigger ON jobs;")
    op.execute("DROP FUNCTION IF EXISTS jobs_search_vector_update();")
