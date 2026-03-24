from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database import get_session
from app.routers import plans as plans_router_module
from app.schemas.plan_task import PlanTaskResponse
from main import app


class _FakeSession:
    pass


async def _override_session() -> AsyncGenerator[_FakeSession, None]:
    yield _FakeSession()


def test_get_plan_tasks_route_returns_items(monkeypatch) -> None:
    async def fake_list_plan_tasks(_session, *, limit: int = 30):
        assert limit == 30
        return [
            PlanTaskResponse(
                id="task-1",
                title="StartupIndex source",
                status="started",
                story_points=3,
                message="Checking company pages and role pages",
                link="https://startup-index.ch/en/the-startup-directory/",
                next_step="Pick the clean integration path",
                created_at=datetime(2026, 3, 24, tzinfo=UTC),
                updated_at=datetime(2026, 3, 24, tzinfo=UTC),
            )
        ]

    monkeypatch.setattr(plans_router_module, "list_plan_tasks", fake_list_plan_tasks)
    app.dependency_overrides[get_session] = _override_session
    try:
        client = TestClient(app)
        response = client.get("/api/plans/tasks")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["title"] == "StartupIndex source"
        assert payload["items"][0]["story_points"] == 3
    finally:
        app.dependency_overrides.clear()
