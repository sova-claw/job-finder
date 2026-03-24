from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.scraper import djinni as djinni_module


def test_resolve_djinni_scraper_mode_prefers_explicit_mode(monkeypatch) -> None:
    settings = djinni_module.get_settings()
    monkeypatch.setattr(settings, "external_djinni_scraper_enabled", False)
    monkeypatch.setattr(settings, "djinni_scraper_mode", "external-local")

    assert djinni_module.resolve_djinni_scraper_mode() == "external-local"


def test_resolve_djinni_scraper_mode_falls_back_to_internal_after_canary_window(
    monkeypatch,
) -> None:
    settings = djinni_module.get_settings()
    monkeypatch.setattr(settings, "djinni_scraper_mode", "canary")
    monkeypatch.setattr(
        settings,
        "djinni_canary_until",
        datetime.now(UTC) - timedelta(hours=1),
    )

    mode = djinni_module.resolve_djinni_scraper_mode(now=datetime.now(UTC))

    assert mode == "internal"


@pytest.mark.asyncio
async def test_scrape_djinni_uses_external_local_mode(monkeypatch) -> None:
    external = AsyncMock(
        return_value={
            "source": "Djinni",
            "count_found": 1,
            "count_new": 1,
            "count_skipped": 0,
        }
    )
    settings = djinni_module.get_settings()
    monkeypatch.setattr(settings, "djinni_scraper_mode", "external-local")
    monkeypatch.setattr(settings, "external_djinni_scraper_enabled", False)
    monkeypatch.setattr(djinni_module, "scrape_external_djinni", external)

    summary = await djinni_module.scrape_djinni(session=object())

    external.assert_awaited_once()
    assert summary["count_found"] == 1


@pytest.mark.asyncio
async def test_scrape_djinni_canary_uses_external_primary_and_internal_shadow(monkeypatch) -> None:
    external = AsyncMock(
        return_value={
            "source": "Djinni",
            "count_found": 5,
            "count_new": 2,
            "count_skipped": 3,
        }
    )
    internal = AsyncMock(
        return_value={
            "source": "Djinni",
            "count_found": 4,
            "count_candidates": 3,
            "count_new": 0,
            "count_skipped": 0,
        }
    )
    settings = djinni_module.get_settings()
    monkeypatch.setattr(settings, "djinni_scraper_mode", "canary")
    monkeypatch.setattr(
        settings,
        "djinni_canary_until",
        datetime.now(UTC) + timedelta(hours=23),
    )
    monkeypatch.setattr(djinni_module, "scrape_external_djinni", external)
    monkeypatch.setattr(djinni_module, "_scrape_internal_djinni", internal)
    session = object()

    summary = await djinni_module.scrape_djinni(session=session)

    external.assert_awaited_once()
    internal.assert_awaited_once_with(session, persist=False)
    assert summary["count_found"] == 5
    assert summary["details"] == [
        "Mode: canary · external-local primary",
        "Shadow internal: 3 matched / 4 found",
        "Found delta: +1",
    ]
