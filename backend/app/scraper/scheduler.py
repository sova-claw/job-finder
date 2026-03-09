from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.database import SessionLocal
from app.scraper.djinni import scrape_djinni
from app.scraper.dou import scrape_dou

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

    def start(self) -> None:
        if self._started:
            return
        self.scheduler.add_job(
            lambda: asyncio.create_task(self.run_dou_job()),
            "interval",
            hours=settings.dou_scrape_interval_hours,
            id="scrape-dou",
            replace_existing=True,
        )
        self.scheduler.add_job(
            lambda: asyncio.create_task(self.run_djinni_job()),
            "interval",
            hours=settings.djinni_scrape_interval_hours,
            id="scrape-djinni",
            replace_existing=True,
        )
        self.scheduler.start()
        self._started = True

    def stop(self) -> None:
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False


scheduler_service = SchedulerService()
