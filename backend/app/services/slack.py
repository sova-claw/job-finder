from __future__ import annotations

import json
import re
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


@dataclass(slots=True)
class SlackInboxSummary:
    channel: str
    count_rows: int
    posted_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ScraperRunSummary:
    source: str
    status: str
    duration_seconds: float
    count_found: int = 0
    count_new: int = 0
    count_skipped: int = 0
    count_failed: int = 0
    error: str | None = None
    reported_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ScraperScheduleEntry:
    source: str
    cadence: str
    next_run_at: datetime | None


@dataclass(slots=True)
class ScraperScheduleSummary:
    channel: str
    count_jobs: int
    posted_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class JobSlackChannelSummary:
    job_id: str
    channel_id: str
    channel_name: str
    channel_url: str
    created: bool
    created_at: datetime | None = None


def _job_channel_member_ids() -> list[str]:
    return [
        member_id.strip()
        for member_id in settings.slack_job_channel_member_ids_csv.split(",")
        if member_id.strip()
    ]


async def _invite_members_to_channel(
    client: AsyncWebClient,
    channel_id: str,
    member_ids: list[str],
) -> None:
    for member_id in member_ids:
        try:
            await client.conversations_invite(channel=channel_id, users=member_id)
        except SlackApiError as exc:
            if exc.response.get("error") not in {
                "already_in_channel",
                "cant_invite_self",
                "user_is_bot",
                "already_in_team",
            }:
                raise


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


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value.ljust(width)
    if width <= 1:
        return value[:width]
    return f"{value[: width - 1]}…"


def _priority_label(job: Job) -> str:
    score = job.match_score or 0
    if score >= 75:
        return "P1"
    if score >= 60:
        return "P2"
    return "P3"


def _normalize_channel_name(channel: str) -> str:
    return channel.strip().lstrip("#")


def _build_channel_url(channel_id: str) -> str:
    return f"https://slack.com/app_redirect?channel={channel_id}"


def _slugify_channel_part(value: str | None, *, fallback: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return normalized or fallback


def build_job_channel_name(job: Job) -> str:
    prefix = _slugify_channel_part(settings.slack_job_channel_prefix, fallback="job")
    company = _slugify_channel_part(job.company, fallback="company")
    title = _slugify_channel_part(job.title, fallback="role")
    suffix = _slugify_channel_part(job.id, fallback="job")[:8]
    stem = f"{prefix}-{company}-{title}"
    max_stem_length = max(1, 80 - len(suffix) - 1)
    trimmed = stem[:max_stem_length].rstrip("-")
    return f"{trimmed}-{suffix}"


def build_job_channel_payload(job: Job, *, channel_name: str) -> dict[str, object]:
    score = f"{job.match_score or 0}"
    salary = _format_salary(job)
    location = _format_location(job)
    top_gap = derive_top_gap(job.gaps) or "No major gap"
    company = job.company or "Unknown company"
    title = job.title or "Untitled role"

    return {
        "text": f"Job workspace ready: {title} at {company}",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{title} @ {company}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"Slack channel `#{channel_name}` is now the workspace for this role.\n"
                        "Use it for research, recruiter outreach, prep notes, and next actions."
                    ),
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Score*\n{score}"},
                    {"type": "mrkdwn", "text": f"*Salary*\n{salary}"},
                    {"type": "mrkdwn", "text": f"*Location*\n{location}"},
                    {"type": "mrkdwn", "text": f"*Top gap*\n{top_gap}"},
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


def build_job_channel_topic(job: Job) -> str:
    company = job.company or "Unknown company"
    title = job.title or "Untitled role"
    location = _format_location(job)
    topic = f"{company} | {title} | score {job.match_score or 0} | {location}"
    return topic[:250]


def _channel_overrides() -> dict[str, str]:
    raw = settings.slack_channel_overrides_json.strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("SLACK_CHANNEL_OVERRIDES_JSON must be a JSON object")
    return {_normalize_channel_name(key): str(value) for key, value in parsed.items()}


async def _resolve_or_create_public_channel_id(
    client: AsyncWebClient,
    channel_name: str,
    *,
    cache: dict[str, str],
) -> str:
    try:
        return await _resolve_channel_id(
            client,
            channel_name,
            cache=cache,
            types="public_channel",
        )
    except RuntimeError:
        normalized = _normalize_channel_name(channel_name)
        try:
            response = await client.conversations_create(name=normalized, is_private=False)
        except SlackApiError as exc:
            if exc.response.get("error") != "name_taken":
                raise
            return await _resolve_channel_id(
                client,
                channel_name,
                cache=cache,
                types="public_channel",
            )
        channel_id = str(response["channel"]["id"])
        cache[normalized] = channel_id
        return channel_id


def should_auto_create_job_channel(job: Job) -> bool:
    if not settings.slack_auto_create_job_channels:
        return False
    if job.dealbreaker:
        return False
    return (job.match_score or 0) >= settings.slack_job_channel_min_score


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

    actions: list[dict[str, object]] = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Open job"},
            "url": job.url,
        }
    ]
    if job.slack_channel_id:
        actions.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Open workspace"},
                "url": _build_channel_url(job.slack_channel_id),
            }
        )

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
                "elements": actions,
            },
        ],
    }


def build_jobs_inbox_payload(jobs: list[Job]) -> dict[str, object]:
    if not jobs:
        table = "No active jobs in the inbox right now."
    else:
        jobs = sorted(
            jobs,
            key=lambda job: (
                job.match_score or 0,
                job.posted_at or job.scraped_at or datetime.min.replace(tzinfo=UTC),
            ),
            reverse=True,
        )
        header = (
            f"{'Date':<10}  {'Fit':<10}  {'Pri':<3}  {'Salary':<14}  {'Source':<10}  "
            f"{'Company':<18}  {'Role':<28}"
        )
        separator = (
            f"{'-' * 10}  {'-' * 10}  {'-' * 3}  {'-' * 14}  {'-' * 10}  "
            f"{'-' * 18}  {'-' * 28}"
        )
        rows = [header, separator]
        for job in jobs:
            added_date = (job.scraped_at or job.posted_at or datetime.now(UTC)).date().isoformat()
            rows.append(
                "  ".join(
                    [
                        _truncate(added_date, 10),
                        _truncate(_fit_signal(job), 10),
                        _priority_label(job).ljust(3),
                        _truncate(_format_salary(job), 14),
                        _truncate(job.source or "n/a", 10),
                        _truncate(job.company or "Unknown", 18),
                        _truncate(job.title or "Untitled role", 28),
                    ]
                )
            )
        table = "```" + "\n".join(rows) + "```"

    return {
        "text": "Jobs inbox snapshot",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Jobs inbox ({len(jobs)} roles)"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Compact backlog view with fit, salary, priority, and source.\n"
                        f"{table}"
                    ),
                },
            },
        ],
    }


def build_scraper_run_payload(summary: ScraperRunSummary) -> dict[str, object]:
    status_label = "Success" if summary.status == "success" else "Failed"
    duration = f"{summary.duration_seconds:.1f}s"
    blocks: list[dict[str, object]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Scraper run · {summary.source}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status*\n{status_label}"},
                {"type": "mrkdwn", "text": f"*Duration*\n{duration}"},
                {"type": "mrkdwn", "text": f"*Found*\n{summary.count_found}"},
                {"type": "mrkdwn", "text": f"*New*\n{summary.count_new}"},
                {"type": "mrkdwn", "text": f"*Skipped*\n{summary.count_skipped}"},
                {"type": "mrkdwn", "text": f"*Failed items*\n{summary.count_failed}"},
            ],
        },
    ]

    if summary.error:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error*\n{summary.error}",
                },
            }
        )

    return {
        "text": f"Scraper run: {summary.source} ({status_label.lower()})",
        "blocks": blocks,
    }


def _format_next_run(next_run_at: datetime | None) -> str:
    if next_run_at is None:
        return "Not scheduled"
    normalized = next_run_at.astimezone(UTC)
    return normalized.strftime("%Y-%m-%d %H:%M UTC")


def build_scraper_schedule_payload(entries: list[ScraperScheduleEntry]) -> dict[str, object]:
    rows = [
        "Source           Cadence            Next run (UTC)",
        "---------------  -----------------  --------------------",
    ]
    for entry in entries:
        rows.append(
            "  ".join(
                [
                    _truncate(entry.source, 15),
                    _truncate(entry.cadence, 17),
                    _truncate(_format_next_run(entry.next_run_at), 20),
                ]
            )
        )

    table = "```" + "\n".join(rows) + "```"
    return {
        "text": "Scraper scheduler snapshot",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Scraper scheduler"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Current scraper cadence and next scheduled runs.\n"
                        f"{table}"
                    ),
                },
            },
        ],
    }


def _fit_signal(job: Job) -> str:
    score = job.match_score
    if score is None:
        return "? unscored"
    if score >= 80:
        return "OK strong"
    if score >= 55:
        return "! partial"
    return "X skip"


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


async def list_inbox_jobs(session: AsyncSession, *, limit: int = 25) -> list[Job]:
    query: Select[tuple[Job]] = (
        select(Job)
        .where(
            Job.is_active.is_(True),
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
    types: str = "public_channel",
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
            types=types,
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


async def ensure_job_slack_channel(
    session: AsyncSession,
    job: Job,
    *,
    client: AsyncWebClient | None = None,
) -> JobSlackChannelSummary:
    if not settings.slack_bot_token:
        raise RuntimeError("SLACK_BOT_TOKEN is required to create per-job Slack channels.")

    if job.slack_channel_id and job.slack_channel_name:
        return JobSlackChannelSummary(
            job_id=job.id,
            channel_id=job.slack_channel_id,
            channel_name=job.slack_channel_name,
            channel_url=_build_channel_url(job.slack_channel_id),
            created=False,
            created_at=job.slack_channel_created_at,
        )

    slack_client = client or AsyncWebClient(token=settings.slack_bot_token)
    channel_name = build_job_channel_name(job)
    created = False

    try:
        response = await slack_client.conversations_create(name=channel_name, is_private=False)
        channel = response["channel"]
        channel_id = channel["id"]
        created = True
    except SlackApiError as exc:
        if exc.response.get("error") != "name_taken":
            raise RuntimeError(
                f"Slack channel creation failed: {exc.response.get('error', 'unknown_error')}"
            ) from exc
        cache: dict[str, str] = {}
        channel_id = await _resolve_channel_id(
            slack_client,
            channel_name,
            cache=cache,
            types="public_channel,private_channel",
        )

    try:
        await slack_client.conversations_join(channel=channel_id)
    except SlackApiError as exc:
        if exc.response.get("error") not in {"already_in_channel", "is_archived"}:
            raise

    try:
        await slack_client.conversations_setTopic(
            channel=channel_id,
            topic=build_job_channel_topic(job),
        )
    except SlackApiError:
        pass

    member_ids = _job_channel_member_ids()
    if member_ids:
        await _invite_members_to_channel(slack_client, channel_id, member_ids)

    if created:
        await slack_client.chat_postMessage(
            channel=channel_id,
            **build_job_channel_payload(job, channel_name=channel_name),
        )

    created_at = datetime.now(UTC)
    job.slack_channel_id = channel_id
    job.slack_channel_name = channel_name
    job.slack_channel_created_at = created_at
    await session.commit()
    await session.refresh(job)

    return JobSlackChannelSummary(
        job_id=job.id,
        channel_id=channel_id,
        channel_name=channel_name,
        channel_url=_build_channel_url(channel_id),
        created=created,
        created_at=job.slack_channel_created_at,
    )


async def dispatch_job_to_slack(
    session: AsyncSession,
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
    if should_auto_create_job_channel(job):
        await ensure_job_slack_channel(session, job, client=slack_client)
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
        channels = await dispatch_job_to_slack(
            session,
            job,
            client=client,
            channel_cache=channel_cache,
        )
        if not channels:
            summary.count_skipped += 1
            continue
        job.slack_notified_at = summary.dispatched_at
        await session.commit()
        summary.count_posted += 1

    return summary


async def post_jobs_inbox_snapshot(session: AsyncSession) -> SlackInboxSummary:
    if not settings.slack_bot_token:
        raise RuntimeError(
            "Slack multichannel routing is not configured. "
            "Set SLACK_BOT_TOKEN to post the inbox snapshot."
        )

    jobs = await list_inbox_jobs(session)
    client = AsyncWebClient(token=settings.slack_bot_token)
    await _post_to_channel(
        client,
        "#jobs-inbox",
        build_jobs_inbox_payload(jobs),
        cache={},
    )
    return SlackInboxSummary(channel="#jobs-inbox", count_rows=len(jobs))


async def post_scraper_run_report(
    summary: ScraperRunSummary,
    *,
    client: AsyncWebClient | None = None,
) -> ScraperRunSummary:
    if not settings.slack_bot_token:
        raise RuntimeError("SLACK_BOT_TOKEN is required to post scraper run reports.")

    channel_name = settings.slack_scraper_report_channel.strip()
    if not channel_name:
        return summary

    slack_client = client or AsyncWebClient(token=settings.slack_bot_token)
    cache: dict[str, str] = {}
    channel_id = await _resolve_or_create_public_channel_id(
        slack_client,
        channel_name,
        cache=cache,
    )
    try:
        await slack_client.conversations_join(channel=channel_id)
    except SlackApiError as exc:
        if exc.response.get("error") not in {"already_in_channel", "is_archived"}:
            raise
    await slack_client.chat_postMessage(
        channel=channel_id,
        **build_scraper_run_payload(summary),
    )
    return summary


async def post_scraper_schedule_snapshot(
    entries: list[ScraperScheduleEntry],
    *,
    client: AsyncWebClient | None = None,
) -> ScraperScheduleSummary:
    if not settings.slack_bot_token:
        raise RuntimeError("SLACK_BOT_TOKEN is required to post scraper scheduler updates.")

    channel_name = settings.slack_scraper_report_channel.strip()
    if not channel_name:
        raise RuntimeError(
            "SLACK_SCRAPER_REPORT_CHANNEL must be set to post scraper scheduler updates."
        )

    slack_client = client or AsyncWebClient(token=settings.slack_bot_token)
    cache: dict[str, str] = {}
    channel_id = await _resolve_or_create_public_channel_id(
        slack_client,
        channel_name,
        cache=cache,
    )
    try:
        await slack_client.conversations_join(channel=channel_id)
    except SlackApiError as exc:
        if exc.response.get("error") not in {"already_in_channel", "is_archived"}:
            raise
    await slack_client.chat_postMessage(
        channel=channel_id,
        **build_scraper_schedule_payload(entries),
    )
    return ScraperScheduleSummary(channel=channel_name, count_jobs=len(entries))
