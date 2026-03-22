from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from urllib.parse import quote

import httpx


class AirtableClient:
    def __init__(
        self,
        *,
        pat: str,
        base_id: str,
        timeout_seconds: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url="https://api.airtable.com/v0",
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {pat}"},
        )
        self.base_id = base_id

    async def __aenter__(self) -> AirtableClient:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def list_records(
        self,
        table_name: str,
        *,
        view: str | None = None,
        filter_formula: str | None = None,
        page_size: int = 100,
    ) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        async for record in self.iter_records(
            table_name,
            view=view,
            filter_formula=filter_formula,
            page_size=page_size,
        ):
            records.append(record)
        return records

    async def iter_records(
        self,
        table_name: str,
        *,
        view: str | None = None,
        filter_formula: str | None = None,
        page_size: int = 100,
    ) -> AsyncIterator[dict[str, object]]:
        offset: str | None = None
        encoded_table = quote(table_name, safe="")
        while True:
            params: dict[str, object] = {"pageSize": page_size}
            if view:
                params["view"] = view
            if filter_formula:
                params["filterByFormula"] = filter_formula
            if offset:
                params["offset"] = offset

            payload = await self._request_json(
                "GET",
                f"/{self.base_id}/{encoded_table}",
                params=params,
            )
            for record in payload.get("records", []):
                if isinstance(record, dict):
                    yield record
            next_offset = payload.get("offset")
            if not isinstance(next_offset, str) or not next_offset:
                break
            offset = next_offset

    async def _request_json(
        self,
        method: str,
        path: str,
        **kwargs: object,
    ) -> dict[str, object]:
        last_response: httpx.Response | None = None
        for attempt in range(4):
            response = await self._client.request(method, path, **kwargs)
            last_response = response
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 3:
                    response.raise_for_status()
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Airtable response is not a JSON object")
            return payload

        if last_response is None:
            raise RuntimeError("Airtable request failed before receiving a response")
        last_response.raise_for_status()
        raise RuntimeError("Unreachable Airtable request state")
