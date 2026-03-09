from __future__ import annotations

from datetime import UTC, datetime

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.job import JobDetail, JobSummary, SourceGroup
from app.scraper.common import ScrapedPosting, fetch_html, save_scraped_posting


def normalize_source_group(url: str) -> SourceGroup:
    lowered = url.lower()
    if any(token in lowered for token in ("dou.ua", "djinni.co", ".ua/")):
        return "Ukraine"
    if any(token in lowered for token in ("ycombinator", "workatastartup", "hn", "angel")):
        return "Startups"
    if any(token in lowered for token in ("linkedin", "indeed", "remoteok")):
        return "Global"
    return "BigCo"


async def fetch_job_page(url: str) -> tuple[str, str]:
    html = await fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    title = soup.title.text.strip() if soup.title and soup.title.text else url
    return title, text


async def upsert_job_from_url(session: AsyncSession, url: str) -> tuple[object, bool]:
    title, raw_text = await fetch_job_page(url)
    posting = ScrapedPosting(
        url=url,
        source="Manual",
        source_group=normalize_source_group(url),
        title=title,
        company="Manual import",
        posted_at=datetime.now(UTC),
        raw_text=raw_text,
    )
    job, is_new = await save_scraped_posting(session, posting)
    await session.commit()
    await session.refresh(job)
    return job, is_new


def to_job_summary(job: object) -> JobSummary:
    return JobSummary.model_validate(job)


def to_job_detail(job: object) -> JobDetail:
    return JobDetail.model_validate(job)
