from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.schemas.job import JobDetail, JobSummary, SourceGroup, Verdict
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


def derive_top_gap(gaps: list[dict[str, Any]] | None) -> str | None:
    if not gaps:
        return None
    first_gap = gaps[0]
    return first_gap.get("skill")


def derive_verdict(match_score: int | None) -> Verdict:
    if match_score is None:
        return "not_aligned"
    if match_score >= 85:
        return "apply_now"
    if match_score >= 75:
        return "prepare_first"
    return "not_aligned"


def serialize_job(job: Job) -> dict[str, Any]:
    slack_channel_url = (
        f"https://slack.com/app_redirect?channel={job.slack_channel_id}"
        if job.slack_channel_id
        else None
    )
    return {
        "id": job.id,
        "url": job.url,
        "source": job.source,
        "source_group": job.source_group,
        "title": job.title,
        "company": job.company,
        "company_type": job.company_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "tags": job.tags,
        "domain": job.domain,
        "remote": job.remote,
        "location": job.location,
        "match_score": job.match_score,
        "hard_matches": job.hard_matches,
        "soft_matches": job.soft_matches,
        "dealbreaker": job.dealbreaker,
        "top_gap": derive_top_gap(job.gaps),
        "verdict": derive_verdict(job.match_score),
        "posted_at": job.posted_at,
        "scraped_at": job.scraped_at,
        "scored_at": job.scored_at,
        "slack_channel_id": job.slack_channel_id,
        "slack_channel_name": job.slack_channel_name,
        "slack_channel_url": slack_channel_url,
        "slack_channel_created_at": job.slack_channel_created_at,
        "is_active": job.is_active,
        "raw_text": job.raw_text,
        "requirements_must": job.requirements_must,
        "requirements_nice": job.requirements_nice,
        "gaps": job.gaps,
        "extracted_at": job.extracted_at,
    }


async def fetch_job_page(url: str) -> tuple[str, str]:
    html = await fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    title = soup.title.text.strip() if soup.title and soup.title.text else url
    return title, text


async def upsert_job_from_url(session: AsyncSession, url: str) -> tuple[Job, bool]:
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


def to_job_summary(job: Job) -> JobSummary:
    return JobSummary.model_validate(serialize_job(job))


def to_job_detail(job: Job) -> JobDetail:
    return JobDetail.model_validate(serialize_job(job))
