from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database import get_session
from app.routers import alerts as alerts_router_module
from app.services.slack import ScraperScheduleSummary, SlackDispatchSummary, SlackInboxSummary
from main import app


class _FakeSession:
    pass


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
