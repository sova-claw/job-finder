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


def test_build_job_channel_name_is_slack_safe() -> None:
    name = slack.build_job_channel_name(
        _job(
            id="job_123456789",
            company="monday.com",
            title="Senior QA / Automation Engineer (Python)",
        )
    )

    assert name.startswith("job-monday-com-senior-qa-automation-engineer-python-")
    assert len(name) <= 80
    assert "/" not in name


@pytest.mark.asyncio
async def test_ensure_job_slack_channel_creates_and_persists(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_bot_token", "xoxb-test")

    calls: list[tuple[str, dict[str, object]]] = []

    class FakeClient:
        async def conversations_create(self, *, name: str, is_private: bool):
            calls.append(("create", {"name": name, "is_private": is_private}))
            return {"channel": {"id": "C123", "name": name}}

        async def conversations_join(self, *, channel: str):
            calls.append(("join", {"channel": channel}))
            return {"ok": True}

        async def conversations_setTopic(self, *, channel: str, topic: str):
            calls.append(("topic", {"channel": channel, "topic": topic}))
            return {"ok": True}

        async def chat_postMessage(self, *, channel: str, **payload):
            calls.append(("post", {"channel": channel, "payload": payload}))
            return {"ok": True}

    class FakeSession:
        def __init__(self) -> None:
            self.commits = 0
            self.refreshed = 0

        async def commit(self) -> None:
            self.commits += 1

        async def refresh(self, _job: Job) -> None:
            self.refreshed += 1

    job = _job(id="job-42", company="Sentry", title="Senior QA Automation Engineer")
    session = FakeSession()

    summary = await slack.ensure_job_slack_channel(session, job, client=FakeClient())  # type: ignore[arg-type]

    assert summary.job_id == "job-42"
    assert summary.channel_id == "C123"
    assert summary.channel_name == job.slack_channel_name
    assert summary.channel_url == "https://slack.com/app_redirect?channel=C123"
    assert summary.created is True
    assert session.commits == 1
    assert session.refreshed == 1
    assert job.slack_channel_id == "C123"
    assert job.slack_channel_name is not None
    assert [name for name, _payload in calls] == ["create", "join", "topic", "post"]


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
