from datetime import UTC, datetime

import pytest

from app.models.job import Job
from app.services import slack


def _job(**overrides: object) -> Job:
    payload = {
        "id": "job-1",
        "url": "https://example.com/jobs/1",
        "source": "Djinni",
        "source_group": "BigCo",
        "title": "Senior QA Automation Engineer",
        "company": "Bolt",
        "salary_min": 6000,
        "salary_max": 8000,
        "location": "Poland",
        "match_score": 82,
        "hard_matches": ["Python", "QA Automation"],
        "soft_matches": ["UI Automation", "CI/CD"],
        "dealbreaker": False,
        "gaps": [{"skill": "Playwright", "current": 60, "target": 100, "weeks_to_close": 4}],
        "posted_at": datetime(2026, 3, 22, tzinfo=UTC),
        "scored_at": datetime(2026, 3, 22, tzinfo=UTC),
        "is_active": True,
    }
    payload.update(overrides)
    return Job(**payload)


def test_build_slack_payload_contains_key_fields() -> None:
    payload = slack.build_slack_payload(_job(), routed_channels=["#jobs-poland"])

    assert payload["text"] == "New CIS job: Senior QA Automation Engineer at Bolt"
    blocks = payload["blocks"]
    assert isinstance(blocks, list)
    assert any("Playwright" in field["text"] for field in blocks[1]["fields"])
    assert any("Python, QA Automation" in field["text"] for field in blocks[1]["fields"])
    assert any("#jobs-poland" in field["text"] for field in blocks[1]["fields"])


@pytest.mark.asyncio
async def test_dispatch_new_jobs_to_slack_marks_jobs_notified(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(slack.settings, "slack_max_posts_per_run", 10)

    jobs = [_job(), _job(id="job-2", url="https://example.com/jobs/2", company="Agoda")]
    routed_jobs: list[str] = []

    async def fake_list_pending_jobs(_session, *, limit: int):
        assert limit == 10
        return jobs

    async def fake_dispatch_job(job: Job, *, client=None, channel_cache=None) -> list[str]:
        del client, channel_cache
        routed_jobs.append(job.id)
        return ["#jobs-poland"]

    class FakeSession:
        def __init__(self) -> None:
            self.commits = 0

        async def commit(self) -> None:
            self.commits += 1

    session = FakeSession()
    monkeypatch.setattr(slack, "list_pending_slack_jobs", fake_list_pending_jobs)
    monkeypatch.setattr(slack, "dispatch_job_to_slack", fake_dispatch_job)

    summary = await slack.dispatch_new_jobs_to_slack(session)  # type: ignore[arg-type]

    assert summary.count_found == 2
    assert summary.count_posted == 2
    assert session.commits == 2
    assert all(job.slack_notified_at is not None for job in jobs)
    assert routed_jobs == ["job-1", "job-2"]
