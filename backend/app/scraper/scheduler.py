from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal
from app.scraper.apify_linkedin import scrape_apify_linkedin
from app.scraper.bigco import scrape_bigco
from app.scraper.careers_page import scrape_careers_pages
from app.scraper.djinni import scrape_djinni
from app.scraper.dou import scrape_dou
from app.scraper.hn_jobs import scrape_hn_jobs
from app.services.company_sync import sync_airtable_companies
from app.services.slack import (
    ScraperRunSummary,
    ScraperScheduleEntry,
    ScraperScheduleSummary,
    dispatch_new_jobs_to_slack,
    post_scraper_run_report,
    post_scraper_schedule_snapshot,
)

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScheduledScraper:
    job_id: str
    source: str
    cadence: str


SCRAPER_SCHEDULES = (
    ScheduledScraper(
        "scrape-dou",
        "DOU",
        f"Every {settings.dou_scrape_interval_hours} hours",
    ),
    ScheduledScraper(
        "scrape-djinni",
        "Djinni",
        f"Every {settings.djinni_scrape_interval_hours} hours",
    ),
    ScheduledScraper("scrape-bigco", "BigCo", "Weekly"),
    ScheduledScraper("scrape-careers-page", "CareersPage", "Weekly"),
    ScheduledScraper("scrape-linkedin", "LinkedIn", "Daily"),
    ScheduledScraper("scrape-hn", "HN", "Every 4 weeks"),
)


class SchedulerService:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._started = False

    async def _run_scraper_job(
        self,
        *,
        source: str,
        scrape_fn: Callable[[AsyncSession], Awaitable[dict[str, object]]],
    ) -> None:
        started = perf_counter()
        async with SessionLocal() as session:
            try:
                summary = await scrape_fn(session)
                logger.info("scrape complete", extra=summary)
                await self._post_scraper_summary(
                    ScraperRunSummary(
                        source=summary.get("source", source),
                        status="success",
                        duration_seconds=perf_counter() - started,
                        count_found=summary.get("count_found", 0),
                        count_new=summary.get("count_new", 0),
                        count_skipped=summary.get("count_skipped", 0),
                        count_failed=summary.get("count_failed", 0),
                        details=list(summary.get("details", [])),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("%s scrape failed: %s", source, exc)
                await self._post_scraper_summary(
                    ScraperRunSummary(
                        source=source,
                        status="failed",
                        duration_seconds=perf_counter() - started,
                        error=str(exc),
                    )
                )

    async def _post_scraper_summary(self, summary: ScraperRunSummary) -> None:
        try:
            await post_scraper_run_report(summary)
        except RuntimeError:
            logger.info("Scraper Slack reporting skipped because Slack is not configured")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scraper Slack reporting failed: %s", exc)

    def _build_schedule_entries(self) -> list[ScraperScheduleEntry]:
        entries: list[ScraperScheduleEntry] = []
        for scraper in SCRAPER_SCHEDULES:
            job = self.scheduler.get_job(scraper.job_id)
            entries.append(
                ScraperScheduleEntry(
                    source=scraper.source,
                    cadence=scraper.cadence,
                    next_run_at=getattr(job, "next_run_time", None),
                )
            )
        return entries

    async def post_schedule_snapshot(self) -> ScraperScheduleSummary | None:
        try:
            return await post_scraper_schedule_snapshot(self._build_schedule_entries())
        except RuntimeError:
            logger.info("Scraper schedule Slack reporting skipped because Slack is not configured")
            return None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scraper schedule Slack reporting failed: %s", exc)
            return None

    async def run_dou_job(self) -> None:
        await self._run_scraper_job(source="DOU", scrape_fn=scrape_dou)

    async def run_djinni_job(self) -> None:
        await self._run_scraper_job(source="Djinni", scrape_fn=scrape_djinni)

    async def run_bigco_job(self) -> None:
        await self._run_scraper_job(source="BigCo", scrape_fn=scrape_bigco)

    async def run_careers_page_job(self) -> None:
        await self._run_scraper_job(source="CareersPage", scrape_fn=scrape_careers_pages)

    async def run_linkedin_job(self) -> None:
        await self._run_scraper_job(source="LinkedIn", scrape_fn=scrape_apify_linkedin)

    async def run_hn_job(self) -> None:
        await self._run_scraper_job(source="HN", scrape_fn=scrape_hn_jobs)

    async def run_airtable_sync_job(self) -> None:
        async with SessionLocal() as session:
            try:
                summary = await sync_airtable_companies(session)
                logger.info(
                    "airtable sync complete",
                    extra={
                        "count_found": summary.count_found,
                        "count_created": summary.count_created,
                        "count_updated": summary.count_updated,
                        "count_skipped": summary.count_skipped,
                    },
                )
            except RuntimeError:
                logger.info("Airtable sync skipped because Airtable is not configured")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Airtable sync failed: %s", exc)

    async def run_slack_job(self) -> None:
        async with SessionLocal() as session:
            try:
                summary = await dispatch_new_jobs_to_slack(session)
                logger.info(
                    "slack dispatch complete",
                    extra={
                        "count_found": summary.count_found,
                        "count_posted": summary.count_posted,
                        "count_skipped": summary.count_skipped,
                    },
                )
            except RuntimeError:
                logger.info("Slack dispatch skipped because Slack is not configured")
            except Exception as exc:  # noqa: BLE001
                logger.exception("Slack dispatch failed: %s", exc)

    def start(self) -> None:
        if self._started:
            return
        self.scheduler.add_job(
            self.run_dou_job,
            "interval",
            hours=settings.dou_scrape_interval_hours,
            id="scrape-dou",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.run_djinni_job,
            "interval",
            hours=settings.djinni_scrape_interval_hours,
            id="scrape-djinni",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.run_bigco_job,
            "interval",
            weeks=1,
            id="scrape-bigco",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.run_careers_page_job,
            "interval",
            weeks=1,
            id="scrape-careers-page",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.run_linkedin_job,
            "interval",
            days=1,
            id="scrape-linkedin",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.run_hn_job,
            "interval",
            weeks=4,
            id="scrape-hn",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.run_airtable_sync_job,
            "interval",
            minutes=settings.airtable_sync_interval_minutes,
            id="sync-airtable",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.run_slack_job,
            "interval",
            minutes=settings.slack_post_interval_minutes,
            id="notify-slack",
            replace_existing=True,
        )
        self.scheduler.start()
        self._started = True

    def stop(self) -> None:
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False


scheduler_service = SchedulerService()
