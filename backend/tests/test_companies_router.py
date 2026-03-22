from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database import get_session
from app.routers import companies as companies_router_module
from app.schemas.company import CompanySummary
from main import app


class _FakeSession:
    pass


async def _override_session() -> AsyncGenerator[_FakeSession, None]:
    yield _FakeSession()


def test_companies_route_returns_company_payload(monkeypatch) -> None:
    async def fake_list_companies(_session, **_filters):
        return (
            [
                CompanySummary(
                    id="company-1",
                    airtable_record_id="rec123",
                    name="Bolt",
                    country="Poland",
                    city="Warsaw",
                    geo_bucket="poland",
                    track_fit_sdet=True,
                    track_fit_ai=True,
                    brand_tier="Tier 1",
                    salary_hypothesis="6k-8k",
                    careers_url="https://bolt.eu/careers",
                    linkedin_url="https://linkedin.com/company/bolt",
                    priority="High",
                    status="Target",
                    notes="Strong product brand",
                    openings_count=2,
                    priority_score=87,
                    recommended_action="Review openings and apply",
                    last_synced_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            ],
            1,
        )

    monkeypatch.setattr(companies_router_module, "list_companies", fake_list_companies)
    app.dependency_overrides[get_session] = _override_session
    try:
        client = TestClient(app)
        response = client.get("/api/companies")
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["name"] == "Bolt"
        assert payload["items"][0]["priority_score"] == 87
    finally:
        app.dependency_overrides.clear()


def test_sync_airtable_route_handles_missing_config(monkeypatch) -> None:
    async def fake_sync(_session):
        raise RuntimeError("Airtable is not configured")

    monkeypatch.setattr(companies_router_module, "sync_airtable_companies", fake_sync)
    app.dependency_overrides[get_session] = _override_session
    try:
        client = TestClient(app)
        response = client.post("/api/sync/airtable")
        assert response.status_code == 503
        assert response.json()["detail"] == "Airtable is not configured"
    finally:
        app.dependency_overrides.clear()
