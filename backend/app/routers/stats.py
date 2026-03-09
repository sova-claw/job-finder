from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
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
    result = await session.execute(select(Job))
    jobs = result.scalars().all()
    gap_counter: Counter[str] = Counter()
    source_breakdown: Counter[str] = Counter()
    total_score = 0
    scored_jobs = 0
    high_pay_count = 0
    active_jobs = 0

    for job in jobs:
        source_breakdown[job.source_group] += 1
        if job.is_active:
            active_jobs += 1
        if job.match_score is not None:
            total_score += job.match_score
            scored_jobs += 1
        if job.salary_max and job.salary_max >= 10_000:
            high_pay_count += 1
        for gap in job.gaps or []:
            skill = gap.get("skill")
            if skill:
                gap_counter[skill] += 1

    return JobStats(
        total_jobs=len(jobs),
        active_jobs=active_jobs,
        avg_score=round(total_score / scored_jobs, 1) if scored_jobs else 0.0,
        high_pay_count=high_pay_count,
        top_gap=gap_counter.most_common(1)[0][0] if gap_counter else None,
        source_breakdown=dict(source_breakdown),
    )


@router.get("/profile", response_model=CandidateProfile)
async def get_profile() -> CandidateProfile:
    return get_candidate_profile()


@router.get("/market", response_model=MarketInsight)
async def get_market_insight(session: AsyncSession = Depends(get_session)) -> MarketInsight:
    result = await session.execute(select(Job))
    jobs = result.scalars().all()
    return build_market_insight(jobs)
