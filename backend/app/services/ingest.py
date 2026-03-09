from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.job import Job
from app.schemas.job import JobDetail, JobSummary, SourceGroup
from app.services.extractor import extract_job_details
from app.services.profile import get_candidate_profile
from app.services.scorer import score_job

settings = get_settings()


def normalize_source_group(url: str) -> SourceGroup:
    lowered = url.lower()
    if any(token in lowered for token in ("dou.ua", "djinni.co", "ua")):
        return "Ukraine"
    if any(token in lowered for token in ("ycombinator", "workatastartup", "hn", "angel")):
        return "Startups"
    if any(token in lowered for token in ("linkedin", "indeed", "remoteok")):
        return "Global"
    return "BigCo"


def job_id_for(company: str, title: str, posted_at: datetime | None) -> str:
    key = f"{company}|{title}|{posted_at.isoformat() if posted_at else 'unknown'}"
    return hashlib.md5(key.encode("utf-8"), usedforsecurity=False).hexdigest()


async def fetch_job_page(url: str) -> tuple[str, str]:
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        follow_redirects=True,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    title = soup.title.text.strip() if soup.title and soup.title.text else url
    return title, text


async def upsert_job_from_url(session: AsyncSession, url: str) -> Job:
    title, raw_text = await fetch_job_page(url)
    extraction = await extract_job_details(raw_text, url=url, source="")
    score, gaps = score_job(extraction, get_candidate_profile())
    now = datetime.now(UTC)
    job_id = job_id_for(extraction.company, extraction.title or title, now)

    existing = await session.execute(select(Job).where(Job.url == url))
    job = existing.scalar_one_or_none()
    if job is None:
        job = Job(
            id=job_id or str(uuid4()),
            url=url,
            source=extraction.company,
            source_group=normalize_source_group(url),
            raw_text=raw_text,
        )
        session.add(job)

    job.title = extraction.title or title
    job.company = extraction.company
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
    job.posted_at = now
    job.scraped_at = now
    job.extracted_at = now
    job.is_active = True

    await session.commit()
    await session.refresh(job)
    return job


def to_job_summary(job: Job) -> JobSummary:
    return JobSummary.model_validate(job)


def to_job_detail(job: Job) -> JobDetail:
    return JobDetail.model_validate(job)
