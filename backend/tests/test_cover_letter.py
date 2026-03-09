from datetime import UTC, datetime

import pytest

from app.models.job import Job
from app.services.cover_letter import generate_cover_letter


class FakeResult:
    def scalar_one_or_none(self):
        return None


class FakeSession:
    def __init__(self) -> None:
        self.records = []

    async def execute(self, _query):
        return FakeResult()

    def add(self, record):
        self.records.append(record)

    async def commit(self):
        return None

    async def refresh(self, record):
        record.created_at = datetime.now(UTC)


@pytest.mark.asyncio
async def test_generate_cover_letter_fallback() -> None:
    session = FakeSession()
    job = Job(
        id="job-1",
        url="https://example.com/jobs/1",
        source="Example",
        source_group="Global",
        raw_text="Python, FastAPI, AI",
        title="Senior Python AI Engineer",
        company="Example",
        tags=["Python", "FastAPI", "AI"],
        requirements_must=["Python", "FastAPI"],
        requirements_nice=[],
        is_active=True,
    )

    response = await generate_cover_letter(session, job, "professional")

    assert response.job_id == "job-1"
    assert response.cached is False
    assert "Example" in response.letter
    assert response.profile_tags_used
