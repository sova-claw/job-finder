from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

from app.database import get_session
from main import app


class _FakeSession:
    async def execute(self, _query: object) -> int:
        return 1


async def _override_session() -> AsyncGenerator[_FakeSession, None]:
    yield _FakeSession()


def test_health_returns_ok() -> None:
    app.dependency_overrides[get_session] = _override_session
    try:
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "db": "connected"}
    finally:
        app.dependency_overrides.clear()
