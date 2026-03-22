from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database import get_session
from app.routers import alerts as alerts_router_module
from app.services.slack import SlackDispatchSummary
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
