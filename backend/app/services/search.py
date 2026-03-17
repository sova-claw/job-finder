from sqlalchemy import Select, String, asc, desc, func, or_, select

from app.models.job import Job


def build_job_query(
    *,
    source_group: str | None = None,
    search: str | None = None,
    sort_by: str = "match_score",
    sort_dir: str = "desc",
) -> Select[tuple[Job]]:
    query: Select[tuple[Job]] = select(Job).where(Job.is_active.is_(True))
    if source_group and source_group != "All":
        query = query.where(Job.source_group == source_group)

    if search:
        ts_query = func.websearch_to_tsquery("english", search)
        query = query.where(
            or_(
                Job.search_vector.op("@@")(ts_query),
                Job.title.ilike(f"%{search}%"),
                Job.company.ilike(f"%{search}%"),
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

    if getattr(column.type, "python_type", None) is str or isinstance(column.type, String):
        query = query.order_by(ordering(func.coalesce(column, "")))
    else:
        query = query.order_by(ordering(column).nullslast())
    return query
