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
    Weight("Python", 15, ("python",), 0),
    Weight("Cloud GCP/AWS", 10, ("gcp", "aws", "cloud"), 0),
    Weight("Docker", 8, ("docker",), 0),
    Weight("SQL + Pandas/NumPy", 8, ("sql", "pandas", "numpy"), 0),
    Weight("English B2+", 7, ("english",), 0),
    Weight("ETL / data pipelines", 5, ("etl", "pipeline", "airflow", "kafka"), 0),
    Weight("LLM APIs", 12, ("llm", "anthropic", "openai"), 1),
    Weight("LangChain / agents", 10, ("langchain", "agent"), 2),
    Weight("RAG + Vector DB", 10, ("rag", "vector", "pgvector"), 2),
    Weight("FastAPI production", 7, ("fastapi",), 1),
    Weight("Production ML (1y+)", 8, ("machine learning", "ml", "model"), 4),
)

PROFILE_STRENGTH = {
    "Python": 100,
    "Cloud GCP/AWS": 100,
    "Docker": 100,
    "SQL + Pandas/NumPy": 100,
    "English B2+": 100,
    "ETL / data pipelines": 100,
    "LLM APIs": 42,
    "LangChain / agents": 30,
    "RAG + Vector DB": 0,
    "FastAPI production": 57,
    "Production ML (1y+)": 25,
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
        return min(weight, max(0, round(weight * 0.8)))
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
