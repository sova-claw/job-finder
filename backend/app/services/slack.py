from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.job import Job
from app.services.ingest import derive_top_gap
from app.services.router import route_channels_for_job

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


def _format_matches(matches: list[str] | None) -> str:
    if not matches:
        return "n/a"
    return ", ".join(matches)


def _normalize_channel_name(channel: str) -> str:
    return channel.strip().lstrip("#")


def _channel_overrides() -> dict[str, str]:
    raw = settings.slack_channel_overrides_json.strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("SLACK_CHANNEL_OVERRIDES_JSON must be a JSON object")
    return {_normalize_channel_name(key): str(value) for key, value in parsed.items()}


def build_slack_payload(job: Job, *, routed_channels: list[str] | None = None) -> dict[str, object]:
    title = job.title or "Untitled role"
    company = job.company or "Unknown company"
    score = f"{job.match_score or 0}"
    salary = _format_salary(job)
    top_gap = derive_top_gap(job.gaps) or "No major gap"
    location = _format_location(job)
    source = f"{job.source_group} / {job.source}"
    posted_at = job.posted_at.date().isoformat() if job.posted_at else "n/a"
    hard_matches = _format_matches(job.hard_matches)
    soft_matches = _format_matches(job.soft_matches)
    routed = ", ".join(routed_channels or []) or "n/a"

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
                    {"type": "mrkdwn", "text": f"*Score*\n{score}"},
                    {"type": "mrkdwn", "text": f"*Salary*\n{salary}"},
                    {"type": "mrkdwn", "text": f"*Location*\n{location}"},
                    {"type": "mrkdwn", "text": f"*Source*\n{source}"},
                    {"type": "mrkdwn", "text": f"*Hard matches*\n{hard_matches}"},
                    {"type": "mrkdwn", "text": f"*Soft matches*\n{soft_matches}"},
                    {"type": "mrkdwn", "text": f"*Top gap*\n{top_gap}"},
                    {"type": "mrkdwn", "text": f"*Posted*\n{posted_at}"},
                    {"type": "mrkdwn", "text": f"*Routed*\n{routed}"},
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
            Job.scored_at.is_not(None),
            Job.slack_notified_at.is_(None),
            Job.source != "Manual",
            or_(Job.dealbreaker.is_(False), Job.dealbreaker.is_(None)),
        )
        .order_by(
            Job.match_score.desc().nullslast(),
            Job.posted_at.desc().nullslast(),
            Job.scraped_at.desc(),
        )
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def _resolve_channel_id(
    client: AsyncWebClient,
    channel_name: str,
    *,
    cache: dict[str, str],
) -> str:
    normalized = _normalize_channel_name(channel_name)
    if normalized in cache:
        return cache[normalized]

    overrides = _channel_overrides()
    if normalized in overrides:
        cache[normalized] = overrides[normalized]
        return cache[normalized]

    cursor: str | None = None
    while True:
        response = await client.conversations_list(
            limit=1000,
            cursor=cursor,
            exclude_archived=True,
            types="public_channel",
        )
        for channel in response.get("channels", []):
            name = channel.get("name")
            channel_id = channel.get("id")
            if not name or not channel_id:
                continue
            cache.setdefault(name, channel_id)
            if name == normalized:
                return channel_id
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    raise RuntimeError(
        f"Slack channel {channel_name} is not resolvable. "
        "Add it as a public channel, grant the bot groups:read for private-channel discovery, "
        "or set SLACK_CHANNEL_OVERRIDES_JSON with explicit channel IDs."
    )


async def _post_to_channel(
    client: AsyncWebClient,
    channel_name: str,
    payload: dict[str, object],
    *,
    cache: dict[str, str],
) -> None:
    channel_id = await _resolve_channel_id(client, channel_name, cache=cache)
    try:
        await client.conversations_join(channel=channel_id)
    except SlackApiError as exc:
        error = exc.response.get("error")
        allowed_errors = {
            "already_in_channel",
            "method_not_supported_for_channel_type",
            "is_archived",
        }
        if error not in allowed_errors:
            raise
    await client.chat_postMessage(channel=channel_id, **payload)


async def dispatch_job_to_slack(
    job: Job,
    *,
    client: AsyncWebClient | None = None,
    channel_cache: dict[str, str] | None = None,
) -> list[str]:
    channels = route_channels_for_job(job)
    if not channels:
        return []
    if not settings.slack_bot_token:
        raise RuntimeError(
            "SLACK_BOT_TOKEN is required for named-channel routing. "
            "Legacy single-webhook delivery cannot target planner channels."
        )

    slack_client = client or AsyncWebClient(token=settings.slack_bot_token)
    cache = channel_cache if channel_cache is not None else {}
    payload = build_slack_payload(job, routed_channels=channels)
    for channel in channels:
        await _post_to_channel(slack_client, channel, payload, cache=cache)
    return channels


async def dispatch_new_jobs_to_slack(session: AsyncSession) -> SlackDispatchSummary:
    if not settings.slack_bot_token:
        raise RuntimeError(
            "Slack multichannel routing is not configured. Set SLACK_BOT_TOKEN and, for private "
            "channels, either grant groups:read or provide SLACK_CHANNEL_OVERRIDES_JSON."
        )

    jobs = await list_pending_slack_jobs(session, limit=settings.slack_max_posts_per_run)
    summary = SlackDispatchSummary(count_found=len(jobs))
    client = AsyncWebClient(token=settings.slack_bot_token)
    channel_cache: dict[str, str] = {}
    for job in jobs:
        channels = await dispatch_job_to_slack(job, client=client, channel_cache=channel_cache)
        if not channels:
            summary.count_skipped += 1
            continue
        job.slack_notified_at = summary.dispatched_at
        await session.commit()
        summary.count_posted += 1

    return summary
