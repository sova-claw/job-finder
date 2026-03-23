from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import CompanySnapshot
from app.models.job import Job
from app.models.research import ResearchFinding
from app.schemas.research import CreateResearchFindingRequest, ResearchFindingResponse


@dataclass(slots=True)
class ResearchScope:
    job: Job | None = None
    company: CompanySnapshot | None = None


def _normalize_tags(tags: Sequence[str] | None) -> list[str] | None:
    if not tags:
        return None
    cleaned: list[str] = []
    for tag in tags:
        value = str(tag).strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned or None


def _coerce_evidence(payload: CreateResearchFindingRequest) -> list[dict[str, str]] | None:
    evidence: list[dict[str, str]] = []
    if payload.evidence:
        evidence.extend([item.model_dump(mode="json") for item in payload.evidence])
    if payload.source_url:
        evidence.append(
            {
                "url": payload.source_url,
                "title": payload.source_title or None,
                "source_domain": payload.source_domain or None,
                "snippet": payload.source_snippet or None,
            }
        )
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in evidence:
        url = str(item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(item)
    return deduped or None


async def resolve_research_scope(
    session: AsyncSession,
    *,
    job_id: str | None = None,
    company_id: str | None = None,
) -> ResearchScope:
    job: Job | None = None
    company: CompanySnapshot | None = None
    if job_id:
        job = await session.get(Job, job_id)
        if job is None:
            raise LookupError("Job not found")
        if job.company:
            company_result = await session.execute(
                select(CompanySnapshot).where(
                    func.lower(CompanySnapshot.name) == func.lower(job.company)
                )
            )
            company = company_result.scalar_one_or_none()
    if company_id:
        company = await session.get(CompanySnapshot, company_id)
        if company is None:
            raise LookupError("Company not found")
    return ResearchScope(job=job, company=company)


async def list_job_research(session: AsyncSession, job_id: str) -> list[ResearchFindingResponse]:
    scope = await resolve_research_scope(session, job_id=job_id)
    conditions = [ResearchFinding.job_id == job_id]
    if scope.company is not None:
        conditions.append(ResearchFinding.company_snapshot_id == scope.company.id)
    query = (
        select(ResearchFinding)
        .where(or_(*conditions))
        .order_by(ResearchFinding.created_at.desc())
    )
    result = await session.execute(query)
    items = result.scalars().all()
    return [ResearchFindingResponse.model_validate(item) for item in items]


async def list_company_research(
    session: AsyncSession,
    company_id: str,
) -> list[ResearchFindingResponse]:
    _scope = await resolve_research_scope(session, company_id=company_id)
    result = await session.execute(
        select(ResearchFinding)
        .where(ResearchFinding.company_snapshot_id == company_id)
        .order_by(ResearchFinding.created_at.desc())
    )
    return [ResearchFindingResponse.model_validate(item) for item in result.scalars().all()]


async def create_job_research(
    session: AsyncSession,
    *,
    job_id: str,
    payload: CreateResearchFindingRequest,
) -> ResearchFindingResponse:
    scope = await resolve_research_scope(session, job_id=job_id)
    finding = ResearchFinding(
        id=str(uuid4()),
        job_id=job_id,
        company_snapshot_id=scope.company.id if scope.company else None,
        finding_type=payload.finding_type.strip(),
        title=payload.title.strip(),
        summary=payload.summary.strip(),
        confidence=payload.confidence,
        tags=_normalize_tags(payload.tags),
        evidence=_coerce_evidence(payload),
        source_kind=payload.source_kind.strip(),
        created_by=payload.created_by.strip(),
    )
    session.add(finding)
    await session.commit()
    await session.refresh(finding)
    return ResearchFindingResponse.model_validate(finding)
