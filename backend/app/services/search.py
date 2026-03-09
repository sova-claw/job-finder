from sqlalchemy import Select, asc, desc, func, or_, select

from app.models.job import Job


def build_job_query(
    *,
    source_group: str | None = None,
    search: str | None = None,
    sort_by: str = "match_score",
    sort_dir: str = "desc",
) -> Select[tuple[Job]]:
    query: Select[tuple[Job]] = select(Job)
    if source_group and source_group != "All":
        query = query.where(Job.source_group == source_group)

    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.raw_text.ilike(pattern),
                Job.domain.ilike(pattern),
            )
        )

    sort_columns = {
        "match_score": Job.match_score,
        "salary_max": Job.salary_max,
        "posted_at": Job.posted_at,
        "scraped_at": Job.scraped_at,
        "company": Job.company,
    }
    column = sort_columns.get(sort_by, Job.match_score)
    ordering = asc if sort_dir == "asc" else desc
    query = query.order_by(ordering(func.coalesce(column, 0 if sort_dir == "asc" else -1)))
    return query
