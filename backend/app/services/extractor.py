from __future__ import annotations

import json
import re
from collections.abc import Iterable

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.job import JobExtraction

settings = get_settings()

TAG_CANONICAL = {
    "python": "Python",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "langchain": "LangChain",
    "rag": "RAG",
    "vector": "Vector DB",
    "pgvector": "pgvector",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "sql": "SQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "ml": "ML",
    "machine learning": "ML",
    "llm": "LLM",
    "anthropic": "Anthropic API",
    "openai": "OpenAI API",
    "aws": "AWS",
    "gcp": "GCP",
    "kafka": "Kafka",
    "airflow": "Airflow",
}

DOMAIN_HINTS = {
    "fintech": "FinTech",
    "health": "HealthTech",
    "edtech": "EdTech",
    "web3": "Web3",
    "crypto": "Web3",
    "media": "MediaTech",
    "developer tools": "Developer Tools",
}


def normalize_tag(tag: str) -> str:
    return TAG_CANONICAL.get(tag.strip().lower(), tag.strip())


def infer_company_type(text: str) -> str:
    lowered = text.lower()
    if "startup" in lowered or "seed" in lowered or "series a" in lowered:
        return "Startup"
    if "product" in lowered or "platform" in lowered or "saas" in lowered:
        return "Product"
    if "outsource" in lowered or "client" in lowered or "agency" in lowered:
        return "Service"
    return "Unknown"


def infer_domain(text: str) -> str:
    lowered = text.lower()
    for needle, label in DOMAIN_HINTS.items():
        if needle in lowered:
            return label
    return "General"


def extract_salary(text: str) -> tuple[int | None, int | None]:
    patterns = [
        r"\$?\s?(\d[\d,]{2,})\s*[-–]\s*\$?\s?(\d[\d,]{2,})",
        r"from\s+\$?\s?(\d[\d,]{2,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        numbers = [int(value.replace(",", "")) for value in match.groups() if value]
        if len(numbers) == 2:
            return min(numbers), max(numbers)
        if len(numbers) == 1:
            return numbers[0], None
    return None, None


def extract_bullet_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip(" \t-•*")
        if len(line) < 4:
            continue
        if any(token in raw_line for token in ("-", "•", "*")):
            lines.append(line)
    return lines


def unique_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def heuristic_extract(raw_text: str, *, url: str = "", source: str = "") -> JobExtraction:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    title = lines[0] if lines else "Unknown role"
    company = source or "Unknown company"
    if " at " in title:
        title, company = [part.strip() for part in title.split(" at ", maxsplit=1)]
    elif len(lines) > 1 and len(lines[1]) < 70:
        company = lines[1]

    salary_min, salary_max = extract_salary(raw_text)
    bullets = extract_bullet_lines(raw_text)
    must_haves = [
        bullet
        for bullet in bullets
        if any(token in bullet.lower() for token in TAG_CANONICAL)
    ][:8]
    nice_to_have = [
        bullet
        for bullet in bullets
        if bullet not in must_haves
        and any(token in bullet.lower() for token in ("nice", "plus", "bonus"))
    ][:5]

    tags = []
    for token, canonical in TAG_CANONICAL.items():
        if token in raw_text.lower():
            tags.append(canonical)
    tags = unique_keep_order(tags)[:10]

    remote = "remote" in raw_text.lower()
    location = None
    location_match = re.search(
        r"(Kyiv|Ukraine|Remote|Europe|Poland|Berlin|London|USA)",
        raw_text,
        re.IGNORECASE,
    )
    if location_match:
        location = location_match.group(1)

    if url and company == "Unknown company":
        domain = url.split("/")[2]
        company = domain.split(".")[0].replace("-", " ").title()

    extraction = JobExtraction(
        title=title,
        company=company,
        company_type=infer_company_type(raw_text),
        salary_min=salary_min,
        salary_max=salary_max,
        requirements_must=must_haves,
        requirements_nice=nice_to_have,
        tags=tags,
        domain=infer_domain(raw_text),
        remote=remote,
        location=location,
    )
    return extraction


def build_extraction_prompt(raw_text: str) -> str:
    return (
        "Extract structured data from this job posting. "
        "Respond only with valid JSON matching this schema: "
        "{title, company, company_type, salary_min, salary_max, "
        "requirements_must, requirements_nice, "
        "tags, domain, remote, location}. "
        f"Job posting:\n{raw_text}"
    )


async def anthropic_extract(raw_text: str) -> JobExtraction:
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.anthropic_extractor_model,
        "max_tokens": 1200,
        "temperature": 0,
        "messages": [{"role": "user", "content": build_extraction_prompt(raw_text)}],
    }
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(settings.anthropic_base_url, headers=headers, json=payload)
        response.raise_for_status()
    data = response.json()
    text = "".join(part["text"] for part in data.get("content", []) if part.get("type") == "text")
    parsed = json.loads(text)
    return JobExtraction.model_validate(parsed)


async def extract_job_details(raw_text: str, *, url: str = "", source: str = "") -> JobExtraction:
    if settings.anthropic_api_key:
        for _attempt in range(2):
            try:
                return await anthropic_extract(raw_text)
            except (ValidationError, httpx.HTTPError, json.JSONDecodeError):
                continue
    return heuristic_extract(raw_text, url=url, source=source)
