from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.job import Job
from app.services.extractor import extract_job_details
from app.services.profile import get_candidate_profile
from app.services.scorer import score_job

settings = get_settings()


@dataclass(slots=True)
class ScrapedPosting:
    url: str
    source: str
    source_group: str
    title: str
    company: str
    posted_at: datetime | None
    raw_text: str


def build_job_id(company: str, title: str, posted_at: datetime | None) -> str:
    fingerprint = f"{company}|{title}|{posted_at.isoformat() if posted_at else 'unknown'}"
    return hashlib.md5(fingerprint.encode("utf-8"), usedforsecurity=False).hexdigest()


async def fetch_html(url: str) -> str:
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
    return response.text


async def fetch_text(url: str) -> str:
    html = await fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n", strip=True)


async def save_scraped_posting(session: AsyncSession, posting: ScrapedPosting) -> tuple[Job, bool]:
    job_id = build_job_id(posting.company, posting.title, posting.posted_at)
    existing = await session.execute(select(Job).where(Job.id == job_id))
    job = existing.scalar_one_or_none()
    is_new = job is None
    if job is None:
        job = Job(
            id=job_id,
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
        job.scraped_at = datetime.now(UTC)
        job.is_active = True

    extraction = await extract_job_details(posting.raw_text, url=posting.url, source=posting.source)
    score, gaps = score_job(extraction, get_candidate_profile())
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
    job.match_score = score
    job.gaps = [gap.model_dump(mode="json") for gap in gaps]
    job.extracted_at = datetime.now(UTC)
    return job, is_new
