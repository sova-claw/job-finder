from app.services.search import build_job_query


def test_build_job_query_filters_to_active_jobs() -> None:
    query = build_job_query()

    compiled = str(query)

    assert "jobs.is_active IS true" in compiled
