from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.airtable import AirtableClient
from app.models.company import CompanySnapshot
from app.models.job import Job
from app.schemas.company import CompanyDetail, CompanySummary, Track
from app.services.ingest import to_job_summary

settings = get_settings()


@dataclass(slots=True)
class SyncSummary:
    count_found: int = 0
    count_created: int = 0
    count_updated: int = 0
    count_skipped: int = 0
    synced_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _field_value(fields: dict[str, object], *names: str) -> object | None:
    for name in names:
        value = fields.get(name)
        if value is not None and value != "":
            return value
    return None


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "y", "checked"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _as_str(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        flattened = ", ".join(str(item).strip() for item in value if str(item).strip())
        return flattened or None
    text = str(value).strip()
    return text or None


def _brand_score(value: str | None) -> int:
    mapping = {"Tier 1": 45, "Tier 2": 30, "Tier 3": 18}
    return mapping.get(value or "", 10 if value else 0)


def _priority_weight(value: str | None) -> int:
    mapping = {"High": 24, "Medium": 14, "Low": 6}
    return mapping.get(value or "", 0)


def company_priority_score(company: CompanySnapshot, openings_count: int) -> int:
    score = _brand_score(company.brand_tier)
    score += _priority_weight(company.priority)
    if company.track_fit_sdet:
        score += 8
    if company.track_fit_ai:
        score += 8
    score += min(openings_count, 4) * 5
    return score


def recommended_action(company: CompanySnapshot, openings_count: int) -> str:
    if openings_count > 0 and (company.priority or "").lower() == "high":
        return "Review openings and apply"
    if openings_count > 0:
        return "Check careers page"
    if company.linkedin_url:
        return "Research recruiter path"
    return "Track company and wait for openings"


async def load_existing_companies(session: AsyncSession) -> dict[str, CompanySnapshot]:
    result = await session.execute(select(CompanySnapshot))
    companies = result.scalars().all()
    return {company.airtable_record_id: company for company in companies}


def merge_company_records(
    existing_by_record_id: dict[str, CompanySnapshot],
    records: list[dict[str, object]],
) -> tuple[list[CompanySnapshot], SyncSummary]:
    summary = SyncSummary(count_found=len(records), synced_at=datetime.now(UTC))
    merged: list[CompanySnapshot] = []

    for record in records:
        record_id = _as_str(record.get("id"))
        fields = record.get("fields")
        if not record_id or not isinstance(fields, dict):
            summary.count_skipped += 1
            continue

        name = _as_str(_field_value(fields, "Company", "Name"))
        if not name:
            summary.count_skipped += 1
            continue

        company = existing_by_record_id.get(record_id)
        is_new = company is None
        if company is None:
            company = CompanySnapshot(id=str(uuid4()), airtable_record_id=record_id, name=name)
            summary.count_created += 1
        else:
            summary.count_updated += 1

        company.name = name
        company.country = _as_str(_field_value(fields, "Country"))
        company.city = _as_str(_field_value(fields, "City"))
        company.geo_bucket = _as_str(_field_value(fields, "Geo bucket", "Geo Bucket"))
        company.track_fit_sdet = _as_bool(_field_value(fields, "Track fit SDET", "Track Fit SDET"))
        company.track_fit_ai = _as_bool(_field_value(fields, "Track fit AI", "Track Fit AI"))
        company.brand_tier = _as_str(_field_value(fields, "Brand tier", "Brand Tier"))
        company.salary_hypothesis = _as_str(
            _field_value(fields, "Salary hypothesis", "Salary Hypothesis")
        )
        company.careers_url = _as_str(_field_value(fields, "Careers URL", "Careers Url"))
        company.linkedin_url = _as_str(_field_value(fields, "LinkedIn URL", "Linkedin URL"))
        company.priority = _as_str(_field_value(fields, "Priority"))
        company.status = _as_str(_field_value(fields, "Status"))
        company.notes = _as_str(_field_value(fields, "Notes"))
        company.last_synced_at = summary.synced_at

        if is_new:
            existing_by_record_id[record_id] = company
        merged.append(company)

    return merged, summary


async def sync_airtable_companies(session: AsyncSession) -> SyncSummary:
    if not settings.airtable_pat or not settings.airtable_base_id:
        raise RuntimeError("Airtable is not configured")

    async with AirtableClient(
        pat=settings.airtable_pat,
        base_id=settings.airtable_base_id,
        timeout_seconds=settings.airtable_timeout_seconds,
    ) as client:
        records = await client.list_records(settings.airtable_table_companies)

    existing_by_record_id = await load_existing_companies(session)
    merged, summary = merge_company_records(existing_by_record_id, records)
    for company in merged:
        session.add(company)
    await session.commit()
    return summary


async def list_companies(
    session: AsyncSession,
    *,
    track: Track | None = None,
    country: str | None = None,
    search: str | None = None,
) -> tuple[list[CompanySummary], int]:
    openings_subquery = (
        select(
            func.lower(Job.company).label("company_key"),
            func.count(Job.id).label("openings_count"),
        )
        .where(Job.is_active.is_(True))
        .group_by(func.lower(Job.company))
        .subquery()
    )

    query: Select[tuple[CompanySnapshot, int]] = (
        select(
            CompanySnapshot,
            func.coalesce(openings_subquery.c.openings_count, 0).label("openings_count"),
        )
        .outerjoin(
            openings_subquery,
            func.lower(CompanySnapshot.name) == openings_subquery.c.company_key,
        )
        .order_by(CompanySnapshot.priority.asc().nullslast(), CompanySnapshot.name.asc())
    )

    if track == "sdet_qa":
        query = query.where(CompanySnapshot.track_fit_sdet.is_(True))
    elif track == "ai_engineering":
        query = query.where(CompanySnapshot.track_fit_ai.is_(True))

    if country:
        query = query.where(CompanySnapshot.country.ilike(f"%{country}%"))
    if search:
        query = query.where(
            CompanySnapshot.name.ilike(f"%{search}%")
            | CompanySnapshot.notes.ilike(f"%{search}%")
            | CompanySnapshot.city.ilike(f"%{search}%")
        )

    result = await session.execute(query)
    rows = result.all()
    items = [serialize_company(company, openings_count) for company, openings_count in rows]
    return items, len(items)


async def get_company_detail(session: AsyncSession, company_id: str) -> CompanyDetail | None:
    company = await session.get(CompanySnapshot, company_id)
    if company is None:
        return None

    openings_result = await session.execute(
        select(Job)
        .where(
            Job.is_active.is_(True),
            func.lower(Job.company) == func.lower(company.name),
        )
        .order_by(Job.match_score.desc().nullslast())
        .limit(8)
    )
    related_jobs = [to_job_summary(job) for job in openings_result.scalars().all()]
    return CompanyDetail.model_validate(
        serialize_company(company, len(related_jobs))
        | {"related_jobs": [job.model_dump(mode="json") for job in related_jobs]}
    )


def serialize_company(company: CompanySnapshot, openings_count: int) -> CompanySummary:
    payload = {
        "id": company.id,
        "airtable_record_id": company.airtable_record_id,
        "name": company.name,
        "country": company.country,
        "city": company.city,
        "geo_bucket": company.geo_bucket,
        "track_fit_sdet": company.track_fit_sdet,
        "track_fit_ai": company.track_fit_ai,
        "brand_tier": company.brand_tier,
        "salary_hypothesis": company.salary_hypothesis,
        "careers_url": company.careers_url,
        "linkedin_url": company.linkedin_url,
        "priority": company.priority,
        "status": company.status,
        "notes": company.notes,
        "openings_count": openings_count,
        "priority_score": company_priority_score(company, openings_count),
        "recommended_action": recommended_action(company, openings_count),
        "last_synced_at": company.last_synced_at,
        "updated_at": company.updated_at,
    }
    return CompanySummary.model_validate(payload)
