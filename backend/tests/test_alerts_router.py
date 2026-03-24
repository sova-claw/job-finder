from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database import get_session
from app.routers import alerts as alerts_router_module
from app.services.slack import (
    ScraperScheduleSummary,
    SlackDispatchSummary,
    SlackInboxSummary,
    SlackPlanUpdateSummary,
)
from main import app


class _FakeSession:
    pass


class _FakeTask:
    def __init__(self, *, task_id: str, title: str) -> None:
        self.id = task_id
        self.title = title


async def _override_session() -> AsyncGenerator[_FakeSession, None]:
    yield _FakeSession()


def test_send_slack_alerts_route_returns_summary(monkeypatch) -> None:
    async def fake_dispatch(_session):
        return SlackDispatchSummary(
            count_found=3,
            count_posted=3,
            count_skipped=0,
            dispatched_at=datetime.now(UTC),
        )

    monkeypatch.setattr(alerts_router_module, "dispatch_new_jobs_to_slack", fake_dispatch)
    app.dependency_overrides[get_session] = _override_session
    try:
        client = TestClient(app)
        response = client.post("/api/alerts/slack/send")
        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "Slack"
        assert payload["count_posted"] == 3
    finally:
        app.dependency_overrides.clear()


def test_send_slack_alerts_route_handles_missing_config(monkeypatch) -> None:
    async def fake_dispatch(_session):
        raise RuntimeError("Slack is not configured")

    monkeypatch.setattr(alerts_router_module, "dispatch_new_jobs_to_slack", fake_dispatch)
    app.dependency_overrides[get_session] = _override_session
    try:
        client = TestClient(app)
        response = client.post("/api/alerts/slack/send")
        assert response.status_code == 503
        assert response.json()["detail"] == "Slack is not configured"
    finally:
        app.dependency_overrides.clear()


def test_send_slack_inbox_route_returns_summary(monkeypatch) -> None:
    async def fake_snapshot(_session):
        return SlackInboxSummary(channel="#jobs-inbox", count_rows=12, posted_at=datetime.now(UTC))

    monkeypatch.setattr(alerts_router_module, "post_jobs_inbox_snapshot", fake_snapshot)
    app.dependency_overrides[get_session] = _override_session
    try:
        client = TestClient(app)
        response = client.post("/api/alerts/slack/inbox")
        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "Slack Inbox"
        assert payload["channel"] == "#jobs-inbox"
        assert payload["count_rows"] == 12
    finally:
        app.dependency_overrides.clear()


def test_send_scraper_schedule_route_returns_summary(monkeypatch) -> None:
    async def fake_post_schedule():
        return ScraperScheduleSummary(
            channel="#scraper-runs",
            count_jobs=6,
            posted_at=datetime.now(UTC),
        )

    monkeypatch.setattr(
        alerts_router_module.scheduler_service,
        "post_schedule_snapshot",
        fake_post_schedule,
    )

    client = TestClient(app)
    response = client.post("/api/alerts/slack/scraper-schedule")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "Scraper Scheduler"
    assert payload["channel"] == "#scraper-runs"
    assert payload["count_jobs"] == 6


def test_send_scraper_schedule_route_handles_missing_config(monkeypatch) -> None:
    async def fake_post_schedule():
        raise RuntimeError("Slack is not configured")

    monkeypatch.setattr(
        alerts_router_module.scheduler_service,
        "post_schedule_snapshot",
        fake_post_schedule,
    )

    client = TestClient(app)
    response = client.post("/api/alerts/slack/scraper-schedule")
    assert response.status_code == 503
    assert response.json()["detail"] == "Slack is not configured"


def test_send_plan_update_route_returns_summary(monkeypatch) -> None:
    async def _override_session() -> AsyncGenerator[_FakeSession, None]:
        yield _FakeSession()

    async def fake_save_plan_task(
        _session,
        *,
        title: str,
        status: str,
        story_points: int | None = None,
        message: str | None = None,
        link: str | None = None,
        next_step: str | None = None,
    ):
        assert title == "StartupIndex source"
        assert status == "started"
        assert story_points == 3
        assert message == "StartupIndex discovery source"
        assert link == "https://startup-index.ch/en/the-startup-directory/"
        assert next_step == "Choose the clean integration path"
        return _FakeTask(task_id="task-1", title=title)

    async def fake_post_plan_update(
        *,
        status: str,
        title: str,
        message: str,
        story_points: int | None = None,
        next_step: str | None = None,
        link: str | None = None,
        task_id: str | None = None,
    ):
        assert status == "started"
        assert title == "StartupIndex source"
        assert message == "StartupIndex discovery source"
        assert story_points == 3
        assert next_step == "Choose the clean integration path"
        assert link == "https://startup-index.ch/en/the-startup-directory/"
        assert task_id == "task-1"
        return SlackPlanUpdateSummary(
            channel="#plans",
            status=status,
            task_id=task_id,
            posted_at=datetime.now(UTC),
        )

    monkeypatch.setattr(alerts_router_module, "save_plan_task", fake_save_plan_task)
    monkeypatch.setattr(alerts_router_module, "post_plan_update", fake_post_plan_update)
    app.dependency_overrides[get_session] = _override_session
    client = TestClient(app)
    try:
        response = client.post(
            "/api/alerts/slack/plans",
            json={
                "status": "started",
                "title": "StartupIndex source",
                "story_points": 3,
                "message": "StartupIndex discovery source",
                "link": "https://startup-index.ch/en/the-startup-directory/",
                "next_step": "Choose the clean integration path",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "Slack Plans"
        assert payload["channel"] == "#plans"
        assert payload["status"] == "started"
        assert payload["task_id"] == "task-1"
    finally:
        app.dependency_overrides.clear()


def test_send_plan_update_route_handles_missing_config(monkeypatch) -> None:
    async def _override_session() -> AsyncGenerator[_FakeSession, None]:
        yield _FakeSession()

    async def fake_save_plan_task(
        _session,
        *,
        title: str,
        status: str,
        story_points: int | None = None,
        message: str | None = None,
        link: str | None = None,
        next_step: str | None = None,
    ):
        del _session, title, status, story_points, message, link, next_step
        return _FakeTask(task_id="task-1", title="Slack format")

    async def fake_post_plan_update(
        *,
        status: str,
        title: str,
        message: str,
        story_points: int | None = None,
        next_step: str | None = None,
        link: str | None = None,
        task_id: str | None = None,
    ):
        del status, title, message, story_points, next_step, link, task_id
        raise RuntimeError("Slack is not configured")

    monkeypatch.setattr(alerts_router_module, "save_plan_task", fake_save_plan_task)
    monkeypatch.setattr(alerts_router_module, "post_plan_update", fake_post_plan_update)
    app.dependency_overrides[get_session] = _override_session
    client = TestClient(app)
    try:
        response = client.post(
            "/api/alerts/slack/plans",
            json={
                "status": "done",
                "title": "Slack format",
                "message": "Slack formatting polished",
            },
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Slack is not configured"
    finally:
        app.dependency_overrides.clear()
