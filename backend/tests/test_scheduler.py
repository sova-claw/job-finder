from datetime import UTC, datetime

import pytest

from app.scraper import scheduler
from app.services.slack import ScraperScheduleSummary


class _FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_run_scraper_job_posts_success_summary(monkeypatch) -> None:
    service = scheduler.SchedulerService()
    reported: list[scheduler.ScraperRunSummary] = []

    async def fake_scrape(_session) -> dict[str, int]:
        return {
            "source": "DOU",
            "count_found": 18,
            "count_new": 4,
            "count_skipped": 14,
            "count_failed": 0,
        }

    async def fake_post(summary: scheduler.ScraperRunSummary) -> None:
        reported.append(summary)

    monkeypatch.setattr(scheduler, "SessionLocal", lambda: _FakeSessionContext())
    monkeypatch.setattr(service, "_post_scraper_summary", fake_post)

    await service._run_scraper_job(source="DOU", scrape_fn=fake_scrape)

    assert len(reported) == 1
    assert reported[0].source == "DOU"
    assert reported[0].status == "success"
    assert reported[0].count_found == 18
    assert reported[0].count_new == 4
    assert reported[0].count_skipped == 14
    assert reported[0].count_failed == 0
    assert reported[0].duration_seconds >= 0


@pytest.mark.asyncio
async def test_run_scraper_job_posts_failure_summary(monkeypatch) -> None:
    service = scheduler.SchedulerService()
    reported: list[scheduler.ScraperRunSummary] = []

    async def fake_scrape(_session) -> dict[str, int]:
        raise RuntimeError("network timeout")

    async def fake_post(summary: scheduler.ScraperRunSummary) -> None:
        reported.append(summary)

    monkeypatch.setattr(scheduler, "SessionLocal", lambda: _FakeSessionContext())
    monkeypatch.setattr(service, "_post_scraper_summary", fake_post)

    await service._run_scraper_job(source="Djinni", scrape_fn=fake_scrape)

    assert len(reported) == 1
    assert reported[0].source == "Djinni"
    assert reported[0].status == "failed"
    assert reported[0].error == "network timeout"
    assert reported[0].count_found == 0
    assert reported[0].count_new == 0
    assert reported[0].count_skipped == 0
    assert reported[0].count_failed == 0
    assert reported[0].duration_seconds >= 0


@pytest.mark.asyncio
async def test_post_schedule_snapshot_uses_scheduler_jobs(monkeypatch) -> None:
    service = scheduler.SchedulerService()
    captured: list[list[scheduler.ScraperScheduleEntry]] = []

    class FakeJob:
        def __init__(self, next_run_time):
            self.next_run_time = next_run_time

    next_run = datetime(2026, 3, 24, 9, 30, tzinfo=UTC)

    monkeypatch.setattr(
        service.scheduler,
        "get_job",
        lambda job_id: FakeJob(next_run) if job_id == "scrape-dou" else FakeJob(None),
    )

    async def fake_post(entries: list[scheduler.ScraperScheduleEntry]) -> ScraperScheduleSummary:
        captured.append(entries)
        return ScraperScheduleSummary(channel="#scraper-runs", count_jobs=len(entries))

    monkeypatch.setattr(scheduler, "post_scraper_schedule_snapshot", fake_post)

    summary = await service.post_schedule_snapshot()

    assert summary is not None
    assert summary.channel == "#scraper-runs"
    assert summary.count_jobs == len(scheduler.SCRAPER_SCHEDULES)
    assert captured[0][0].source == "DOU"
    assert captured[0][0].next_run_at == next_run
