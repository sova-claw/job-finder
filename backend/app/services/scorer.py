from __future__ import annotations

from dataclasses import dataclass

from app.schemas.job import Gap, JobExtraction
from app.schemas.profile import CandidateProfile


@dataclass(frozen=True)
class Weight:
    label: str
    weight: int
    synonyms: tuple[str, ...]
    weeks: int


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


def _job_text(extraction: JobExtraction) -> str:
    chunks = extraction.tags + extraction.requirements_must + extraction.requirements_nice
    return " ".join(chunks).lower()


def _has_requirement(text: str, weight: Weight) -> bool:
    return any(token in text for token in weight.synonyms)


def _current_strength(profile: CandidateProfile, label: str) -> int:
    return PROFILE_STRENGTH.get(label, 0)


def _weight_score(label: str, weight: int, current: int, required: bool) -> int:
    if not required:
        return 0
    return round(weight * (current / 100))


def score_job(extraction: JobExtraction, profile: CandidateProfile) -> tuple[int, list[Gap]]:
    text = _job_text(extraction)
    score = 0
    gaps: list[Gap] = []
    for weight in WEIGHTS:
        current = _current_strength(profile, weight.label)
        required = _has_requirement(text, weight)
        score += _weight_score(weight.label, weight.weight, current, required)
        if required and current < 100:
            gaps.append(
                Gap(
                    skill=weight.label,
                    current=current,
                    target=100,
                    weeks_to_close=weight.weeks,
                )
            )
    return min(100, score), sorted(gaps, key=lambda item: (item.weeks_to_close, item.skill))
