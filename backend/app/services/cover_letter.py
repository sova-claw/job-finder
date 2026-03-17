from __future__ import annotations

import json
from uuid import uuid4

import httpx
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.cover_letter import CoverLetter
from app.models.job import Job
from app.schemas.cover_letter import CoverLetterResponse, Tone
from app.services.profile import get_candidate_profile, get_profile_hash

settings = get_settings()

TONE_GUIDANCE = {
    "professional": "Formal, structured, no contractions. 180-220 words.",
    "direct": "Confident, short, facts-first, minimal fluff. 120-150 words.",
    "enthusiastic": "Warmer, company-specific, but still concise. 200-240 words.",
}

COVER_LETTER_SYSTEM_PROMPT = (
    "You write concise, honest cover letters for software engineers. "
    "No generic phrases. No 'I am passionate about'. No 'team player'. "
    "Reference specific technologies from the job description. "
    "Three paragraphs exactly."
)


def _collect_profile_tags(job: Job) -> list[str]:
    profile = get_candidate_profile()
    tags: list[str] = []
    searchable = " ".join((job.title or "", job.raw_text or "", " ".join(job.tags or []))).lower()
    if "python" in searchable:
        tags.append("7y Python")
    if any(
        token in searchable
        for token in ("pytest", "unittest", "test automation", "qa automation", "sdet")
    ):
        tags.append("Automation framework design")
    if any(token in searchable for token in ("playwright", "selenium", "webdriver")):
        tags.append("UI automation depth")
    if any(
        token in searchable
        for token in ("api testing", "postman", "requests", "rest api", "graphql")
    ):
        tags.append("API quality engineering")
    if any(
        token in searchable
        for token in ("gcp", "cloud", "aws", "jenkins", "github actions", "gitlab ci")
    ):
        tags.append("Cloud certified")
    if not tags:
        tags.append(profile.achievements[0])
    return tags


def _fallback_letter(job: Job, tone: Tone, tags_used: list[str]) -> str:
    tone_hint = TONE_GUIDANCE[tone]
    role = job.title or "this role"
    company = job.company or "your team"
    skills = ", ".join(job.tags or ["Python", "Pytest", "API Testing"])[:90]
    paragraph_1 = (
        f"{role} at {company} matches the work I already do as a senior QA automation engineer "
        f"building Python-based quality systems for product teams. {tone_hint}"
    )
    paragraph_2 = (
        f"My strongest overlap is in {skills}. I have hands-on production "
        "experience building automation frameworks, API validation flows, and release "
        "quality gates, and I am actively sharpening those workflows through CIS and related "
        f"delivery work. Relevant profile evidence includes {', '.join(tags_used[:3])}."
    )
    paragraph_3 = (
        f"I would value the chance to contribute to {company}, especially where "
        "reliable Python automation and test engineering support real product outcomes. "
        "If useful, I can walk through how I would approach the "
        f"role priorities in a first conversation."
    )
    return "\n\n".join((paragraph_1, paragraph_2, paragraph_3))


async def _anthropic_letter(job: Job, tone: Tone, tags_used: list[str]) -> str:
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    profile = get_candidate_profile()
    job_payload = json.dumps(
        {
            "title": job.title,
            "company": job.company,
            "tags": job.tags,
            "requirements_must": job.requirements_must,
        }
    )
    similar_wins: list[str] = []
    prompt = (
        f"Write a {tone} cover letter for this application. "
        f"JOB: {job_payload} "
        f"CANDIDATE: {profile.model_dump_json()} "
        f"SIMILAR_WINS: {json.dumps(similar_wins)} "
        f"PROFILE_TAGS_USED: {json.dumps(tags_used)}"
    )
    payload = {
        "model": settings.anthropic_cover_letter_model,
        "temperature": 0.7,
        "max_tokens": 900,
        "system": COVER_LETTER_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(settings.anthropic_base_url, headers=headers, json=payload)
        response.raise_for_status()
    data = response.json()
    return "".join(part["text"] for part in data.get("content", []) if part.get("type") == "text")


async def _get_cached_letter(
    session: AsyncSession,
    job_id: str,
    tone: Tone,
    profile_hash: str,
) -> CoverLetter | None:
    query: Select[tuple[CoverLetter]] = select(CoverLetter).where(
        CoverLetter.job_id == job_id,
        CoverLetter.tone == tone,
        CoverLetter.profile_hash == profile_hash,
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def generate_cover_letter(
    session: AsyncSession,
    job: Job,
    tone: Tone,
) -> CoverLetterResponse:
    profile_hash = get_profile_hash()
    cached = await _get_cached_letter(session, job.id, tone, profile_hash)
    if cached:
        return CoverLetterResponse(
            id=cached.id,
            job_id=cached.job_id,
            tone=tone,
            letter=cached.letter,
            profile_tags_used=list(cached.tags_used or []),
            cached=True,
            created_at=cached.created_at,
        )

    tags_used = _collect_profile_tags(job)
    if settings.anthropic_api_key:
        try:
            letter = await _anthropic_letter(job, tone, tags_used)
        except httpx.HTTPError:
            letter = _fallback_letter(job, tone, tags_used)
    else:
        letter = _fallback_letter(job, tone, tags_used)

    record = CoverLetter(
        id=str(uuid4()),
        job_id=job.id,
        tone=tone,
        profile_hash=profile_hash,
        letter=letter,
        tags_used=tags_used,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    return CoverLetterResponse(
        id=record.id,
        job_id=record.job_id,
        tone=tone,
        letter=record.letter,
        profile_tags_used=list(record.tags_used or []),
        cached=False,
        created_at=record.created_at,
    )
