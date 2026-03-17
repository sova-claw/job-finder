from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.database import SessionLocal
from app.scraper.apify_linkedin import scrape_apify_linkedin
from app.scraper.bigco import scrape_bigco
from app.scraper.djinni import scrape_djinni
from app.scraper.dou import scrape_dou
from app.scraper.hn_jobs import scrape_hn_jobs

settings = get_settings()
logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._started = False

    async def run_dou_job(self) -> None:
        async with SessionLocal() as session:
            try:
                summary = await scrape_dou(session)
                logger.info("scrape complete", extra=summary)
            except Exception as exc:  # noqa: BLE001
                logger.exception("DOU scrape failed: %s", exc)

    async def run_djinni_job(self) -> None:
        async with SessionLocal() as session:
            try:
                summary = await scrape_djinni(session)
                logger.info("scrape complete", extra=summary)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Djinni scrape failed: %s", exc)

    async def run_bigco_job(self) -> None:
        async with SessionLocal() as session:
            try:
                summary = await scrape_bigco(session)
                logger.info("scrape complete", extra=summary)
            except Exception as exc:  # noqa: BLE001
                logger.exception("BigCo scrape failed: %s", exc)

    async def run_linkedin_job(self) -> None:
        async with SessionLocal() as session:
            try:
                summary = await scrape_apify_linkedin(session)
                logger.info("scrape complete", extra=summary)
            except Exception as exc:  # noqa: BLE001
                logger.exception("LinkedIn scrape failed: %s", exc)

    async def run_hn_job(self) -> None:
        async with SessionLocal() as session:
            try:
                summary = await scrape_hn_jobs(session)
                logger.info("scrape complete", extra=summary)
            except Exception as exc:  # noqa: BLE001
                logger.exception("HN scrape failed: %s", exc)

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
        self.scheduler.start()
        self._started = True

    def stop(self) -> None:
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False


scheduler_service = SchedulerService()
