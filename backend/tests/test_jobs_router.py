from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database import get_session
from app.models.job import Job
from app.routers import jobs as jobs_router_module
from app.services.slack import JobSlackChannelSummary
from main import app


class _Result:
    def __init__(self, job: Job | None) -> None:
        self._job = job

    def scalar_one_or_none(self) -> Job | None:
        return self._job


class _FakeSession:
    def __init__(self, job: Job | None) -> None:
        self.job = job

    async def execute(self, _query) -> _Result:
        return _Result(self.job)


def _job() -> Job:
    return Job(
        id="job-1",
        url="https://example.com/jobs/1",
        source="BigCo",
        source_group="BigCo",
        title="Senior QA Automation Engineer",
        company="Example",
        is_active=True,
    )


def test_create_job_slack_channel_route_returns_channel(monkeypatch) -> None:
    async def _override_session() -> AsyncGenerator[_FakeSession, None]:
        yield _FakeSession(_job())

    async def fake_ensure(_session, _job: Job) -> JobSlackChannelSummary:
        return JobSlackChannelSummary(
            job_id=_job.id,
            channel_id="C123",
            channel_name="job-example-senior-qa-automation-engineer-job-1",
            channel_url="https://slack.com/app_redirect?channel=C123",
            created=True,
            created_at=datetime(2026, 3, 23, tzinfo=UTC),
        )

    monkeypatch.setattr(jobs_router_module, "ensure_job_slack_channel", fake_ensure)
    app.dependency_overrides[get_session] = _override_session
    try:
        client = TestClient(app)
        response = client.post("/api/jobs/job-1/slack-channel")
        assert response.status_code == 200
        payload = response.json()
        assert payload["job_id"] == "job-1"
        assert payload["channel_id"] == "C123"
        assert payload["created"] is True
    finally:
        app.dependency_overrides.clear()
