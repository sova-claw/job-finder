from unittest.mock import AsyncMock

import pytest

from app.scraper import djinni as djinni_module


@pytest.mark.asyncio
async def test_scrape_djinni_uses_external_adapter_when_enabled(monkeypatch) -> None:
    external = AsyncMock(
        return_value={
            "source": "Djinni",
            "count_found": 1,
            "count_new": 1,
            "count_skipped": 0,
        }
    )
    monkeypatch.setattr(
        djinni_module.get_settings(),
        "external_djinni_scraper_enabled",
        True,
    )
    monkeypatch.setattr(djinni_module, "scrape_external_djinni", external)

    summary = await djinni_module.scrape_djinni(session=object())

    external.assert_awaited_once()
    assert summary["count_found"] == 1
