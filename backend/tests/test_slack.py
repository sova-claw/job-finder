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

    assert payload["text"] == "🟢 Bolt — Senior QA Automation Engineer"
    blocks = payload["blocks"]
    assert isinstance(blocks, list)
    body = blocks[0]["text"]["text"]
    assert "Playwright" in body
    assert "Python, QA Automation" in body
    assert "#jobs-poland" in body


def test_build_slack_payload_adds_workspace_button_when_channel_exists() -> None:
    payload = slack.build_slack_payload(
        _job(slack_channel_id="C999"),
        routed_channels=["#jobs-priority"],
    )

    actions = payload["blocks"][1]["elements"]
    assert any(action.get("text", {}).get("text") == "Open workspace" for action in actions)


def test_build_jobs_inbox_job_payload_is_compact_and_signal_dense() -> None:
    payload = slack.build_jobs_inbox_job_payload(_job())

    assert payload["text"] == "🟢 Bolt — Senior QA Automation Engineer [P1|82]"
    body = payload["blocks"][0]["text"]["text"]
    assert "🟢 *Bolt* — Senior QA Automation Engineer" in body
    assert "`P1 · 82`" in body
    assert "$6,000-$8,000" in body
    assert "Python" in body
    assert "Djinni" in body
    assert "Poland" in body
    assert payload["blocks"][0]["accessory"]["text"]["text"] == "Open job"


def test_build_jobs_inbox_payload_has_date_salary_priority_and_source() -> None:
    payload = slack.build_jobs_inbox_payload([_job()])

    assert payload["text"] == "📥 Jobs inbox · 1"
    body = payload["blocks"][1]["text"]["text"]
    assert "Date" in body
    assert "Fit" in body
    assert "Salary" in body
    assert "P" in body
    assert "Src" in body
    assert "OK strong" in body
    assert "2026-03-22" in body
    assert "Bolt" in body


def test_build_scraper_run_payload_contains_operational_fields() -> None:
    payload = slack.build_scraper_run_payload(
        slack.ScraperRunSummary(
            source="DOU",
            status="success",
            duration_seconds=12.4,
            count_found=18,
            count_new=4,
            count_skipped=14,
            count_failed=0,
        )
    )

    assert payload["text"] == "✅ DOU · success"
    body = payload["blocks"][0]["text"]["text"]
    assert "12.4s" in body
    assert "18 found" in body
    assert "4 new" in body
    assert "Skipped: 14" in body
    assert len(payload["blocks"]) == 1


def test_build_scraper_run_payload_includes_error_only_on_failure() -> None:
    payload = slack.build_scraper_run_payload(
        slack.ScraperRunSummary(
            source="LinkedIn",
            status="failed",
            duration_seconds=7.2,
            count_failed=1,
            error="network timeout",
        )
    )

    assert payload["text"] == "⚠️ LinkedIn · failed"
    assert len(payload["blocks"]) == 3
    assert payload["blocks"][1]["elements"][0]["text"] == "Failed items: 1"
    assert payload["blocks"][2]["text"]["text"] == "```network timeout```"


def test_build_scraper_schedule_payload_contains_cadence_and_next_run() -> None:
    payload = slack.build_scraper_schedule_payload(
        [
            slack.ScraperScheduleEntry(
                source="DOU",
                cadence="Every 6 hours",
                next_run_at=datetime(2026, 3, 24, 9, 30, tzinfo=UTC),
            ),
            slack.ScraperScheduleEntry(
                source="LinkedIn",
                cadence="Daily",
                next_run_at=None,
            ),
        ]
    )

    assert payload["text"] == "🕒 Scraper schedule"
    body = payload["blocks"][1]["text"]["text"]
    assert "• *DOU*" in body
    assert "DOU" in body
    assert "Every 6 hours" in body
    assert "2026-03-24 09:30 UTC" in body
    assert "Not scheduled" in body


def test_build_plan_update_payload_is_short_and_structured() -> None:
    payload = slack.build_plan_update_payload(
        status="started",
        title="StartupIndex source",
        message="StartupIndex discovery source",
        story_points=3,
        eta_text="Ends ~14:55",
        link="https://startup-index.ch/en/the-startup-directory/",
        next_step="Choose the clean integration path",
    )

    attachment = payload["attachments"][0]
    assert attachment["color"] == "#1D9E75"
    assert attachment["fallback"] == "🟢 StartupIndex source · Doing"
    blocks = attachment["blocks"]
    assert blocks[0]["type"] == "header"
    assert blocks[0]["text"]["text"] == "🟢  Work started"
    assert blocks[1]["text"]["text"] == "*Task:*  `StartupIndex source`"
    assert blocks[1]["accessory"]["text"]["text"] == "Open"
    assert blocks[1]["accessory"]["url"] == "https://startup-index.ch/en/the-startup-directory/"
    assert blocks[2]["text"]["text"] == "StartupIndex discovery source"
    meta = [item["text"] for item in blocks[3]["elements"]]
    assert meta[0] == "◦ 3 SP"
    assert meta[1].startswith("🕐 ")
    assert meta[2] == "⏱ Ends ~14:55"
    next_meta = [item["text"] for item in blocks[4]["elements"]]
    assert next_meta[0] == "➡️ Next: Choose the clean integration path"


def test_build_plan_update_payload_is_shorter_inside_thread() -> None:
    payload = slack.build_plan_update_payload(
        status="done",
        title="StartupIndex source",
        message="Confirmed it has company pages and apply paths.",
        story_points=3,
        eta_text="Ends ~14:55",
        next_step="Wire the importer.",
        threaded=True,
    )

    attachment = payload["attachments"][0]
    assert attachment["color"] == "#1D9E75"
    assert attachment["fallback"] == "✅ StartupIndex source · Done"
    blocks = attachment["blocks"]
    assert blocks[0]["text"]["text"] == "✅  Task complete"
    assert blocks[1]["text"]["text"] == "*Task:*  `StartupIndex source`"
    assert blocks[2]["text"]["text"] == "Confirmed it has company pages and apply paths."
    meta = [item["text"] for item in blocks[3]["elements"]]
    assert meta[0] == "◦ 3 SP"
    assert meta[1].startswith("🕐 ")
    assert meta[2] == "⏱ Ends ~14:55"
    assert blocks[4]["elements"][0]["text"] == "➡️ Next: Wire the importer."


def test_build_plan_update_payload_info_card_is_simple() -> None:
    payload = slack.build_plan_update_payload(
        status="info",
        title="Task list",
        message="1. Djinni auth scrape\n2. StartupIndex source",
        next_step="Pick one and start.",
    )

    attachment = payload["attachments"][0]
    assert attachment["fallback"] == "🔔 Task list"
    blocks = attachment["blocks"]
    assert blocks[0]["text"]["text"] == "🔔  Task list"
    assert blocks[1]["text"]["text"] == "1. Djinni auth scrape\n2. StartupIndex source"
    assert blocks[2]["type"] == "actions"
    assert blocks[2]["elements"][0]["action_id"] == "plan_pick_task_0"
    assert blocks[2]["elements"][0]["text"]["text"] == "Djinni auth scrape"
    assert blocks[3]["elements"][0]["text"].startswith("🕐 ")
    assert blocks[4]["elements"][0]["text"] == "➡️ Next: Pick one and start."


def test_fit_signal_has_fallbacks_for_score_ranges() -> None:
    assert slack._fit_signal(_job(match_score=82)) == "OK strong"
    assert slack._fit_signal(_job(match_score=60)) == "! partial"
    assert slack._fit_signal(_job(match_score=40)) == "X skip"
    assert slack._fit_signal(_job(match_score=None)) == "? unscored"


def test_build_jobs_inbox_payload_sorts_highest_score_first() -> None:
    payload = slack.build_jobs_inbox_payload(
        [
            _job(company="LowCo", match_score=40),
            _job(company="HighCo", match_score=90),
        ]
    )

    body = payload["blocks"][1]["text"]["text"]

    assert body.index("HighCo") < body.index("LowCo")


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


def test_should_auto_create_job_channel_respects_threshold(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_auto_create_job_channels", True)
    monkeypatch.setattr(slack.settings, "slack_job_channel_min_score", 75)

    assert slack.should_auto_create_job_channel(_job(match_score=75)) is True
    assert slack.should_auto_create_job_channel(_job(match_score=74)) is False


def test_should_auto_create_job_channel_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_auto_create_job_channels", False)
    monkeypatch.setattr(slack.settings, "slack_job_channel_min_score", 75)

    assert slack.should_auto_create_job_channel(_job(match_score=99)) is False


@pytest.mark.asyncio
async def test_ensure_job_slack_channel_creates_and_persists(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(slack.settings, "slack_job_channel_member_ids_csv", "")

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
async def test_ensure_job_slack_channel_invites_members_individually(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(
        slack.settings,
        "slack_job_channel_member_ids_csv",
        "Uhuman,Ubot",
    )

    calls: list[tuple[str, dict[str, object]]] = []

    class FakeInviteError(Exception):
        def __init__(self, error: str) -> None:
            self.response = {"error": error}

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

        async def conversations_invite(self, *, channel: str, users: str):
            calls.append(("invite", {"channel": channel, "users": users}))
            if users == "Ubot":
                raise FakeInviteError("user_is_bot")
            return {"ok": True}

        async def chat_postMessage(self, *, channel: str, **payload):
            calls.append(("post", {"channel": channel, "payload": payload}))
            return {"ok": True}

    class FakeSession:
        async def commit(self) -> None:
            return None

        async def refresh(self, _job: Job) -> None:
            return None

    monkeypatch.setattr(slack, "SlackApiError", FakeInviteError)

    job = _job(id="job-42", company="Sentry", title="Senior QA Automation Engineer")
    await slack.ensure_job_slack_channel(FakeSession(), job, client=FakeClient())  # type: ignore[arg-type]

    invite_calls = [payload["users"] for name, payload in calls if name == "invite"]
    assert invite_calls == ["Uhuman", "Ubot"]


@pytest.mark.asyncio
async def test_dispatch_new_jobs_to_slack_marks_jobs_notified(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(slack.settings, "slack_max_posts_per_run", 10)

    jobs = [_job(), _job(id="job-2", url="https://example.com/jobs/2", company="Agoda")]
    routed_jobs: list[str] = []

    async def fake_list_pending_jobs(_session, *, limit: int):
        assert limit == 10
        return jobs

    async def fake_dispatch_job(
        _session,
        job: Job,
        *,
        client=None,
        channel_cache=None,
    ) -> list[str]:
        del _session, client, channel_cache
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


@pytest.mark.asyncio
async def test_dispatch_job_to_slack_uses_compact_payload_for_jobs_inbox(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_bot_token", "xoxb-test")

    posted: list[tuple[str, dict[str, object]]] = []

    async def fake_post_to_channel(
        _client,
        channel_name: str,
        payload: dict[str, object],
        *,
        cache: dict[str, str],
        thread_ts: str | None = None,
    ) -> dict[str, str]:
        del _client, cache
        assert thread_ts is None
        posted.append((channel_name, payload))
        return {"channel": "C123", "ts": "111.222"}

    monkeypatch.setattr(slack, "_post_to_channel", fake_post_to_channel)

    channels = await slack.dispatch_job_to_slack(
        object(),  # type: ignore[arg-type]
        _job(match_score=60),
        client=object(),  # type: ignore[arg-type]
        channel_cache={},
    )

    assert channels == ["#jobs-inbox"]
    assert posted[0][0] == "#jobs-inbox"
    assert posted[0][1]["text"] == "🟡 Bolt — Senior QA Automation Engineer [P2|60]"
    assert len(posted[0][1]["blocks"]) == 1


@pytest.mark.asyncio
async def test_post_jobs_inbox_snapshot_posts_to_jobs_inbox(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_bot_token", "xoxb-test")

    jobs = [_job(), _job(id="job-2", company="Agoda", source="DOU")]
    posted: list[tuple[str, dict[str, object]]] = []

    async def fake_list_inbox_jobs(_session, *, limit: int = 25):
        assert limit == 25
        return jobs

    async def fake_post_to_channel(
        _client,
        channel_name: str,
        payload: dict[str, object],
        *,
        cache: dict[str, str],
        thread_ts: str | None = None,
    ) -> dict[str, str]:
        del _client, cache
        assert thread_ts is None
        posted.append((channel_name, payload))
        return {"channel": "C123", "ts": "111.222"}

    monkeypatch.setattr(slack, "list_inbox_jobs", fake_list_inbox_jobs)
    monkeypatch.setattr(slack, "_post_to_channel", fake_post_to_channel)

    summary = await slack.post_jobs_inbox_snapshot(object())  # type: ignore[arg-type]

    assert summary.channel == "#jobs-inbox"
    assert summary.count_rows == 2
    assert posted[0][0] == "#jobs-inbox"
    assert posted[0][1]["text"] == "📥 Jobs inbox · 2"


@pytest.mark.asyncio
async def test_post_scraper_run_report_creates_channel_and_posts(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(slack.settings, "slack_scraper_report_channel", "#scraper-runs")

    calls: list[tuple[str, dict[str, object]]] = []

    class FakeClient:
        async def conversations_list(
            self,
            *,
            limit: int,
            cursor: str | None,
            exclude_archived: bool,
            types: str,
        ):
            calls.append(
                (
                    "list",
                    {
                        "limit": limit,
                        "cursor": cursor,
                        "exclude_archived": exclude_archived,
                        "types": types,
                    },
                )
            )
            return {"channels": [], "response_metadata": {"next_cursor": ""}}

        async def conversations_create(self, *, name: str, is_private: bool):
            calls.append(("create", {"name": name, "is_private": is_private}))
            return {"channel": {"id": "C777", "name": name}}

        async def conversations_join(self, *, channel: str):
            calls.append(("join", {"channel": channel}))
            return {"ok": True}

        async def chat_postMessage(self, *, channel: str, **payload):
            calls.append(("post", {"channel": channel, "payload": payload}))
            return {"ok": True}

    summary = await slack.post_scraper_run_report(
        slack.ScraperRunSummary(
            source="DOU",
            status="success",
            duration_seconds=1.4,
            count_found=3,
            count_new=1,
            count_skipped=2,
        ),
        client=FakeClient(),  # type: ignore[arg-type]
    )

    assert summary.source == "DOU"
    assert [name for name, _ in calls] == ["list", "create", "join", "post"]
    assert calls[1][1] == {"name": "scraper-runs", "is_private": False}
    assert calls[3][1]["channel"] == "C777"
    assert calls[3][1]["payload"]["text"] == "✅ DOU · success"


@pytest.mark.asyncio
async def test_post_scraper_schedule_snapshot_creates_channel_and_posts(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_bot_token", "xoxb-test")
    monkeypatch.setattr(slack.settings, "slack_scraper_report_channel", "#scraper-runs")

    calls: list[tuple[str, dict[str, object]]] = []

    class FakeClient:
        async def conversations_list(
            self,
            *,
            limit: int,
            cursor: str | None,
            exclude_archived: bool,
            types: str,
        ):
            calls.append(("list", {"types": types}))
            return {
                "channels": [{"id": "C777", "name": "scraper-runs"}],
                "response_metadata": {"next_cursor": ""},
            }

        async def conversations_join(self, *, channel: str):
            calls.append(("join", {"channel": channel}))
            return {"ok": True}

        async def chat_postMessage(self, *, channel: str, **payload):
            calls.append(("post", {"channel": channel, "payload": payload}))
            return {"ok": True}

    summary = await slack.post_scraper_schedule_snapshot(
        [
            slack.ScraperScheduleEntry(
                source="DOU",
                cadence="Every 6 hours",
                next_run_at=datetime(2026, 3, 24, 9, 30, tzinfo=UTC),
            )
        ],
        client=FakeClient(),  # type: ignore[arg-type]
    )

    assert summary.channel == "#scraper-runs"
    assert summary.count_jobs == 1
    assert [name for name, _ in calls] == ["list", "join", "post"]
    assert calls[0][1] == {"types": "public_channel"}
    assert calls[2][1]["payload"]["text"] == "🕒 Scraper schedule"


@pytest.mark.asyncio
async def test_post_plan_update_posts_to_plans(monkeypatch) -> None:
    monkeypatch.setattr(slack.settings, "slack_bot_token", "xoxb-test")

    posted: list[tuple[str, dict[str, object]]] = []

    async def fake_post_to_channel(
        _client,
        channel_name: str,
        payload: dict[str, object],
        *,
        cache: dict[str, str],
        thread_ts: str | None = None,
    ) -> dict[str, str]:
        del _client, cache
        posted.append((channel_name, payload))
        assert thread_ts is None
        return {"channel": "C123", "ts": "111.222"}

    monkeypatch.setattr(slack, "_post_to_channel", fake_post_to_channel)

    summary = await slack.post_plan_update(
        status="done",
        title="Slack format",
        message="Slack formatting polished",
        story_points=2,
        link="https://example.com/update",
        next_step="StartupIndex discovery source",
        task_id="task-1",
        client=object(),  # type: ignore[arg-type]
    )

    assert summary.channel == "#plans"
    assert summary.status == "done"
    assert summary.task_id == "task-1"
    assert summary.thread_ts == "111.222"
    assert summary.post_ts == "111.222"
    assert posted[0][0] == "#plans"
    assert posted[0][1]["attachments"][0]["fallback"] == "✅ Slack format · Done"


@pytest.mark.asyncio
async def test_post_plan_update_uses_existing_thread(monkeypatch) -> None:
    posted: list[tuple[str, dict[str, object], str | None]] = []

    async def fake_post_to_channel(
        _client,
        channel_name: str,
        payload: dict[str, object],
        *,
        cache: dict[str, str],
        thread_ts: str | None = None,
    ) -> dict[str, str]:
        del _client, cache
        posted.append((channel_name, payload, thread_ts))
        return {"channel": "C123", "ts": "333.444"}

    monkeypatch.setattr(slack, "_post_to_channel", fake_post_to_channel)

    summary = await slack.post_plan_update(
        status="progress",
        title="StartupIndex source",
        message="Found company pages. Checking role pages now.",
        story_points=3,
        task_id="task-1",
        thread_ts="111.222",
        client=object(),  # type: ignore[arg-type]
    )

    assert posted[0][0] == "#plans"
    assert posted[0][2] == "111.222"
    assert (
        posted[0][1]["attachments"][0]["fallback"]
        == "🔵 StartupIndex source · Update"
    )
    assert summary.thread_ts == "111.222"
    assert summary.post_ts == "333.444"
