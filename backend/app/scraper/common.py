from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.job import Job
from app.schemas.job import JobExtraction
from app.services.extractor import extract_job_details
from app.services.profile import (
    get_candidate_profile,
    matches_abroad_remote_preference,
    matches_focus_role,
)
from app.services.scorer import score_job

settings = get_settings()
logger = logging.getLogger(__name__)

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


@dataclass(slots=True)
class ScrapedPosting:
    url: str
    source: str
    source_group: str
    title: str
    company: str
    posted_at: datetime | None
    raw_text: str


def build_job_id(company: str, title: str, posted_at: datetime | None, url: str) -> str:
    identity = posted_at.isoformat() if posted_at else url
    fingerprint = f"{company}|{title}|{identity}"
    return hashlib.md5(fingerprint.encode("utf-8"), usedforsecurity=False).hexdigest()


def parse_posted_at(value: str | None) -> datetime | None:
    if not value:
        return None
    raw_value = re.sub(r"\s+", " ", value.strip())
    iso_candidate = raw_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_candidate)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        pass

    normalized = raw_value.lower()
    now = datetime.now(UTC)

    if "today" in normalized:
        return now
    if "yesterday" in normalized:
        return now - timedelta(days=1)

    relative_match = re.search(r"(\d+)\s+(minute|hour|day|week|month)s?", normalized)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        delta_map = {
            "minute": timedelta(minutes=amount),
            "hour": timedelta(hours=amount),
            "day": timedelta(days=amount),
            "week": timedelta(weeks=amount),
            "month": timedelta(days=30 * amount),
        }
        return now - delta_map[unit]

    date_match = re.search(r"(\d{1,2})\s+([a-z]{3,9})(?:\s+(\d{4}))?", normalized)
    if not date_match:
        return None

    day = int(date_match.group(1))
    month_token = date_match.group(2)[:3]
    month = MONTHS.get(month_token)
    if month is None:
        return None
    year = int(date_match.group(3) or now.year)
    return datetime(year, month, day, tzinfo=UTC)


async def fetch_html(url: str) -> str:
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": settings.scraper_user_agent},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
    return response.text


async def fetch_text(url: str) -> str:
    html = await fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n", strip=True)


async def _render_page(url: str, wait_for: str, *, text_only: bool = False) -> str:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await browser.new_page(user_agent=settings.scraper_user_agent)
        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=int(settings.request_timeout_seconds * 1000),
            )
            await page.wait_for_selector(wait_for, timeout=20_000)
            if text_only:
                return await page.locator("body").inner_text()
            return await page.content()
        finally:
            await browser.close()


async def render_html(url: str, wait_for: str) -> str:
    return await _render_page(url, wait_for)


async def render_text(url: str, wait_for: str) -> str:
    return await _render_page(url, wait_for, text_only=True)


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def dedupe_listings(
    listings: list[tuple[str, str, str, datetime | None]],
) -> list[tuple[str, str, str, datetime | None]]:
    seen_urls: set[str] = set()
    deduped: list[tuple[str, str, str, datetime | None]] = []
    for listing in listings:
        url = listing[0]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(listing)
    return deduped


async def collect_listing_payloads(
    listings: list[tuple[str, str, str, datetime | None]],
    *,
    source: str,
    source_group: str,
    fetch_text_fn: Callable[[str], Awaitable[str]] = fetch_text,
) -> list[ScrapedPosting]:
    semaphore = asyncio.Semaphore(8)

    async def build_posting(
        url: str,
        title: str,
        company: str,
        posted_at: datetime | None,
    ) -> ScrapedPosting | None:
        async with semaphore:
            try:
                raw_text = await fetch_text_fn(url)
            except (httpx.HTTPError, PlaywrightError) as exc:
                logger.warning(
                    "Failed to fetch job detail page",
                    extra={"url": url, "error": str(exc)},
                )
                return None
        return ScrapedPosting(
            url=url,
            source=source,
            source_group=source_group,
            title=title,
            company=company,
            posted_at=posted_at,
            raw_text=raw_text,
        )

    results = await asyncio.gather(
        *[
            build_posting(url, title, company, posted_at)
            for url, title, company, posted_at in listings
        ]
    )
    return [posting for posting in results if posting is not None]


async def update_search_vector(session: AsyncSession, job_id: str) -> None:
    await session.execute(
        text(
            """
            UPDATE jobs
            SET search_vector = to_tsvector(
                'english',
                concat_ws(
                    ' ',
                    coalesce(title, ''),
                    coalesce(company, ''),
                    coalesce(raw_text, ''),
                    coalesce(domain, '')
                )
            )
            WHERE id = :job_id
            """
        ),
        {"job_id": job_id},
    )


async def save_scraped_posting(session: AsyncSession, posting: ScrapedPosting) -> tuple[Job, bool]:
    existing = await session.execute(select(Job).where(Job.url == posting.url))
    job = existing.scalar_one_or_none()
    is_new = job is None
    previous_raw_text = job.raw_text if job is not None else None
    if job is None:
        job = Job(
            id=build_job_id(posting.company, posting.title, posting.posted_at, posting.url),
            url=posting.url,
            source=posting.source,
            source_group=posting.source_group,
            raw_text=posting.raw_text,
            posted_at=posting.posted_at or datetime.now(UTC),
            scraped_at=datetime.now(UTC),
            is_active=True,
        )
        session.add(job)
    else:
        job.raw_text = posting.raw_text
        job.source = posting.source
        job.source_group = posting.source_group
        job.posted_at = posting.posted_at or job.posted_at
        job.scraped_at = datetime.now(UTC)
        job.is_active = True

    raw_text_changed = previous_raw_text != posting.raw_text if not is_new else True
    extraction: JobExtraction | None = None
    needs_extraction = job.extracted_at is None or raw_text_changed
    if needs_extraction:
        extraction = await extract_job_details(
            posting.raw_text,
            url=posting.url,
            source=posting.source,
        )
        job.title = extraction.title or posting.title
        job.company = extraction.company or posting.company
        job.company_type = extraction.company_type
        job.salary_min = extraction.salary_min
        job.salary_max = extraction.salary_max
        job.requirements_must = extraction.requirements_must
        job.requirements_nice = extraction.requirements_nice
        job.tags = extraction.tags
        job.domain = extraction.domain
        job.remote = extraction.remote
        job.location = extraction.location
        job.extracted_at = datetime.now(UTC)
    elif job.title and job.company and job.company_type and job.domain is not None:
        extraction = JobExtraction(
            title=job.title,
            company=job.company,
            company_type=job.company_type,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            requirements_must=job.requirements_must or [],
            requirements_nice=job.requirements_nice or [],
            tags=job.tags or [],
            domain=job.domain,
            remote=bool(job.remote),
            location=job.location,
        )

    if extraction is not None and (needs_extraction or job.scored_at is None):
        scored = await score_job(
            extraction,
            get_candidate_profile(),
            raw_text=posting.raw_text,
        )
        job.match_score = scored.score
        job.hard_matches = scored.hard_matches
        job.soft_matches = scored.soft_matches
        job.dealbreaker = scored.dealbreaker
        job.gaps = [gap.model_dump(mode="json") for gap in scored.gaps]
        job.scored_at = datetime.now(UTC)
        job.is_active = (
            not scored.dealbreaker
            and matches_focus_role(job.title or posting.title, posting.raw_text)
            and matches_abroad_remote_preference(
                title=job.title or posting.title,
                location=job.location,
                raw_text=posting.raw_text,
                remote=job.remote,
            )
        )

    await session.flush()
    await update_search_vector(session, job.id)
    return job, is_new
