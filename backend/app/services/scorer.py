from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.schemas.job import Gap, JobExtraction
from app.schemas.profile import CandidateProfile
from app.services.profile import ScoreRule, get_scoring_rules

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Weight:
    label: str
    weight: int
    synonyms: tuple[str, ...]
    weeks: int


@dataclass(frozen=True)
class JobScore:
    score: int
    hard_matches: list[str]
    soft_matches: list[str]
    dealbreaker: bool
    gaps: list[Gap]


class AnthropicScoreResponse(BaseModel):
    hard_matches: list[str] = Field(default_factory=list)
    soft_matches: list[str] = Field(default_factory=list)
    dealbreaker: bool = False


WEIGHTS: tuple[Weight, ...] = (
    Weight("Python automation", 18, ("python",), 0),
    Weight(
        "QA automation architecture",
        18,
        ("qa automation", "automation qa", "test automation", "sdet", "software engineer in test"),
        0,
    ),
    Weight("Pytest / unittest", 10, ("pytest", "unittest", "nose"), 0),
    Weight("UI automation", 10, ("selenium", "playwright", "webdriver", "cypress"), 1),
    Weight("API testing", 12, ("api testing", "postman", "requests", "rest api", "graphql"), 0),
    Weight(
        "CI/CD quality gates",
        8,
        ("jenkins", "github actions", "gitlab ci", "ci/cd", "pipeline"),
        1,
    ),
    Weight("SQL / data validation", 7, ("sql", "database", "data validation"), 0),
    Weight("Docker / environments", 5, ("docker", "container", "docker compose"), 0),
    Weight("Cloud GCP/AWS", 5, ("gcp", "aws", "cloud"), 0),
    Weight("English B2+", 3, ("english",), 0),
    Weight("Performance testing", 4, ("performance", "load test", "jmeter", "k6"), 2),
)

PROFILE_STRENGTH = {
    "Python automation": 100,
    "QA automation architecture": 95,
    "Pytest / unittest": 90,
    "UI automation": 82,
    "API testing": 95,
    "CI/CD quality gates": 88,
    "SQL / data validation": 88,
    "Docker / environments": 100,
    "Cloud GCP/AWS": 100,
    "English B2+": 100,
    "Performance testing": 35,
}

SCORER_SYSTEM_PROMPT = (
    "You score job postings for a senior Python QA automation candidate. "
    "Use only evidence from the provided job payload. "
    "Respond ONLY with valid JSON matching this schema: "
    '{"hard_matches":["..."],"soft_matches":["..."],"dealbreaker":false}. '
    "Return labels exactly as provided in the scoring rules. "
    "Do not invent labels or add explanations."
)


def _legacy_job_text(extraction: JobExtraction) -> str:
    chunks = [extraction.title, extraction.company, extraction.domain, *extraction.tags]
    chunks.extend(extraction.requirements_must)
    chunks.extend(extraction.requirements_nice)
    return " ".join(chunks).lower()


def _has_requirement(text: str, weight: Weight) -> bool:
    return any(token in text for token in weight.synonyms)


def _current_strength(profile: CandidateProfile, label: str) -> int:
    return PROFILE_STRENGTH.get(label, 0)


def _weight_score(weight: int, current: int, required: bool) -> int:
    if not required:
        return 0
    return round(weight * (current / 100))


def _derive_gaps(extraction: JobExtraction, profile: CandidateProfile) -> list[Gap]:
    text = _legacy_job_text(extraction)
    gaps: list[Gap] = []
    for weight in WEIGHTS:
        current = _current_strength(profile, weight.label)
        required = _has_requirement(text, weight)
        if required and current < 100:
            gaps.append(
                Gap(
                    skill=weight.label,
                    current=current,
                    target=100,
                    weeks_to_close=weight.weeks,
                )
            )
    return sorted(gaps, key=lambda item: (item.weeks_to_close, item.skill))


def _score_from_matches(
    hard_matches: list[str],
    soft_matches: list[str],
    *,
    dealbreaker: bool,
) -> int:
    if dealbreaker:
        return 0
    return min(100, (len(hard_matches) * 30) + (len(soft_matches) * 10))


def _normalize_matches(raw_matches: list[str], rules: tuple[ScoreRule, ...]) -> list[str]:
    allowed = {rule.label: rule for rule in rules}
    normalized: list[str] = []
    for label in raw_matches:
        candidate = label.strip()
        if candidate in allowed and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _match_rules(text: str, rules: tuple[ScoreRule, ...]) -> list[str]:
    matches: list[str] = []
    for rule in rules:
        if any(keyword in text for keyword in rule.keywords):
            matches.append(rule.label)
    return matches


def _build_scoring_prompt(
    extraction: JobExtraction,
    profile: CandidateProfile,
    raw_text: str,
) -> str:
    hard_rules, soft_rules, dealbreaker_rules = get_scoring_rules()
    payload = {
        "job": {
            "title": extraction.title,
            "company": extraction.company,
            "location": extraction.location,
            "remote": extraction.remote,
            "domain": extraction.domain,
            "requirements_must": extraction.requirements_must,
            "requirements_nice": extraction.requirements_nice,
            "tags": extraction.tags,
            "description_excerpt": raw_text[:8000],
        },
        "candidate": {
            "title": profile.title,
            "summary": profile.summary,
            "target_roles": profile.target_roles,
            "strong_skills": profile.strong_skills,
            "working_skills": profile.working_skills,
            "preferred_domains": profile.preferred_domains,
        },
        "scoring_rules": {
            "hard_matches": {rule.label: list(rule.keywords) for rule in hard_rules},
            "soft_matches": {rule.label: list(rule.keywords) for rule in soft_rules},
            "dealbreakers": {rule.label: list(rule.keywords) for rule in dealbreaker_rules},
        },
        "weights": {"hard_match": 30, "soft_match": 10, "dealbreaker": 0},
    }
    return json.dumps(payload, ensure_ascii=True)


def _fallback_score(
    extraction: JobExtraction,
    profile: CandidateProfile,
    *,
    raw_text: str,
) -> JobScore:
    searchable = "\n".join(
        [
            extraction.title,
            extraction.company,
            extraction.location or "",
            extraction.domain,
            " ".join(extraction.tags),
            " ".join(extraction.requirements_must),
            " ".join(extraction.requirements_nice),
            raw_text,
        ]
    ).lower()
    hard_rules, soft_rules, dealbreaker_rules = get_scoring_rules()
    hard_matches = _match_rules(searchable, hard_rules)
    soft_matches = _match_rules(searchable, soft_rules)
    dealbreaker = bool(_match_rules(searchable, dealbreaker_rules))
    gaps = _derive_gaps(extraction, profile)
    return JobScore(
        score=_score_from_matches(hard_matches, soft_matches, dealbreaker=dealbreaker),
        hard_matches=hard_matches,
        soft_matches=soft_matches,
        dealbreaker=dealbreaker,
        gaps=gaps,
    )


async def _anthropic_score(
    extraction: JobExtraction,
    profile: CandidateProfile,
    *,
    raw_text: str,
) -> AnthropicScoreResponse:
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.anthropic_scoring_model,
        "temperature": 0,
        "max_tokens": 700,
        "system": SCORER_SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": _build_scoring_prompt(extraction, profile, raw_text),
            }
        ],
    }
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(settings.anthropic_base_url, headers=headers, json=payload)
        response.raise_for_status()
    data = response.json()
    text_response = "".join(
        part["text"] for part in data.get("content", []) if part.get("type") == "text"
    ).strip()
    parsed = json.loads(text_response)
    return AnthropicScoreResponse.model_validate(parsed)


async def score_job(
    extraction: JobExtraction,
    profile: CandidateProfile,
    *,
    raw_text: str = "",
) -> JobScore:
    hard_rules, soft_rules, _dealbreaker_rules = get_scoring_rules()
    if settings.anthropic_api_key:
        try:
            response = await _anthropic_score(extraction, profile, raw_text=raw_text)
            hard_matches = _normalize_matches(response.hard_matches, hard_rules)
            soft_matches = _normalize_matches(response.soft_matches, soft_rules)
            return JobScore(
                score=_score_from_matches(
                    hard_matches,
                    soft_matches,
                    dealbreaker=response.dealbreaker,
                ),
                hard_matches=hard_matches,
                soft_matches=soft_matches,
                dealbreaker=response.dealbreaker,
                gaps=_derive_gaps(extraction, profile),
            )
        except (ValidationError, httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.warning("Anthropic job scoring failed; falling back", extra={"error": str(exc)})

    return _fallback_score(extraction, profile, raw_text=raw_text)
