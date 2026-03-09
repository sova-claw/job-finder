from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.job import Job
from app.schemas.job import JobStats, MarketInsight
from app.schemas.profile import CandidateProfile
from app.services.market import build_market_insight
from app.services.profile import get_candidate_profile

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=JobStats)
async def get_stats(session: AsyncSession = Depends(get_session)) -> JobStats:
    summary = await session.execute(
        select(
            func.count(Job.id),
            func.count(Job.id).filter(Job.is_active.is_(True)),
            func.avg(Job.match_score),
            func.count(Job.id).filter(
                func.coalesce(Job.salary_max, Job.salary_min, 0) >= 5_000
            ),
        )
    )
    total_jobs, active_jobs, avg_score, high_pay_count = summary.one()

    source_rows = await session.execute(
        select(Job.source_group, func.count(Job.id)).group_by(Job.source_group)
    )
    source_breakdown = {source_group: count for source_group, count in source_rows}

    gaps_rows = await session.execute(select(Job.gaps).where(Job.gaps.is_not(None)))
    gap_counter: Counter[str] = Counter()
    for gaps in gaps_rows.scalars():
        for gap in gaps or []:
            skill = gap.get("skill")
            if skill:
                gap_counter[skill] += 1

    return JobStats(
        total_jobs=total_jobs or 0,
        active_jobs=active_jobs or 0,
        avg_score=round(float(avg_score or 0.0), 1),
        high_pay_count=high_pay_count or 0,
        top_gap=gap_counter.most_common(1)[0][0] if gap_counter else None,
        source_breakdown=source_breakdown,
    )


@router.get("/profile", response_model=CandidateProfile)
async def get_profile() -> CandidateProfile:
    return get_candidate_profile()


@router.get("/market", response_model=MarketInsight)
async def get_market_insight(session: AsyncSession = Depends(get_session)) -> MarketInsight:
    rows = await session.execute(
        select(Job.requirements_must, Job.salary_min, Job.salary_max, Job.remote)
    )
    return build_market_insight(rows.all())
