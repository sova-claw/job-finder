import httpx
import pytest

from app.integrations.airtable import AirtableClient


@pytest.mark.asyncio
async def test_airtable_client_paginates_records() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["Authorization"] == "Bearer test-pat"
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "records": [{"id": "rec1", "fields": {"Company": "Bolt"}}],
                    "offset": "page-2",
                },
            )
        return httpx.Response(
            200,
            json={"records": [{"id": "rec2", "fields": {"Company": "Agoda"}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="https://api.airtable.com/v0",
        headers={"Authorization": "Bearer test-pat"},
    ) as client:
        airtable = AirtableClient(pat="test-pat", base_id="app123", client=client)
        records = await airtable.list_records("Companies")

    assert [record["id"] for record in records] == ["rec1", "rec2"]
