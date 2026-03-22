from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.job import Job
from app.services.ingest import derive_top_gap

settings = get_settings()


@dataclass(slots=True)
class SlackDispatchSummary:
    count_found: int = 0
    count_posted: int = 0
    count_skipped: int = 0
    dispatched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _format_salary(job: Job) -> str:
    if job.salary_min and job.salary_max:
        return f"${job.salary_min:,}-${job.salary_max:,}"
    if job.salary_max:
        return f"Up to ${job.salary_max:,}"
    if job.salary_min:
        return f"From ${job.salary_min:,}"
    return "n/a"


def _format_location(job: Job) -> str:
    if job.location:
        return job.location
    if job.remote:
        return "Remote"
    return "n/a"


def build_slack_payload(job: Job) -> dict[str, object]:
    title = job.title or "Untitled role"
    company = job.company or "Unknown company"
    score = f"{job.match_score or 0}%"
    salary = _format_salary(job)
    top_gap = derive_top_gap(job.gaps) or "No major gap"
    location = _format_location(job)
    source = f"{job.source_group} / {job.source}"
    posted_at = job.posted_at.date().isoformat() if job.posted_at else "n/a"

    return {
        "text": f"New CIS job: {title} at {company}",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{title} @ {company}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Match*\n{score}"},
                    {"type": "mrkdwn", "text": f"*Salary*\n{salary}"},
                    {"type": "mrkdwn", "text": f"*Location*\n{location}"},
                    {"type": "mrkdwn", "text": f"*Source*\n{source}"},
                    {"type": "mrkdwn", "text": f"*Top gap*\n{top_gap}"},
                    {"type": "mrkdwn", "text": f"*Posted*\n{posted_at}"},
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Open job"},
                        "url": job.url,
                    }
                ],
            },
        ],
    }


async def list_pending_slack_jobs(session: AsyncSession, *, limit: int) -> list[Job]:
    query: Select[tuple[Job]] = (
        select(Job)
        .where(
            Job.is_active.is_(True),
            Job.slack_notified_at.is_(None),
            Job.source != "Manual",
            Job.match_score >= settings.slack_min_match_score,
        )
        .order_by(Job.posted_at.desc().nullslast(), Job.scraped_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def post_payload(webhook_url: str, payload: dict[str, object]) -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()


async def dispatch_new_jobs_to_slack(session: AsyncSession) -> SlackDispatchSummary:
    if not settings.slack_webhook_url:
        raise RuntimeError("Slack is not configured")

    jobs = await list_pending_slack_jobs(session, limit=settings.slack_max_posts_per_run)
    summary = SlackDispatchSummary(count_found=len(jobs))
    for job in jobs:
        await post_payload(settings.slack_webhook_url, build_slack_payload(job))
        job.slack_notified_at = summary.dispatched_at
        await session.commit()
        summary.count_posted += 1

    return summary
