from datetime import UTC, datetime

from app.models.job import Job
from app.services.ingest import to_job_detail, to_job_summary


def test_job_summary_derives_top_gap_and_verdict() -> None:
    job = Job(
        id="job-1",
        url="https://example.com/jobs/1",
        source="Example",
        source_group="Global",
        title="Senior Python AI Engineer",
        company="Example",
        salary_min=6000,
        salary_max=9000,
        tags=["Python", "FastAPI"],
        domain="Developer Tools",
        remote=True,
        location="Remote",
        match_score=72,
        gaps=[{"skill": "RAG + Vector DB", "current": 0, "target": 100, "weeks_to_close": 2}],
        posted_at=datetime.now(UTC),
        scraped_at=datetime.now(UTC),
        extracted_at=datetime.now(UTC),
        is_active=True,
    )

    summary = to_job_summary(job)
    detail = to_job_detail(job)

    assert summary.top_gap == "RAG + Vector DB"
    assert summary.verdict == "apply_now"
    assert detail.top_gap == "RAG + Vector DB"
    assert detail.verdict == "apply_now"
