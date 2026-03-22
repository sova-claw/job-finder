from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.company import CompanySnapshot
from app.models.job import Job
from app.schemas.strategy import StrategySnapshot
from app.services.strategy import build_strategy_snapshot

router = APIRouter(tags=["strategy"])


@router.get("/strategy", response_model=StrategySnapshot)
async def strategy_snapshot(session: AsyncSession = Depends(get_session)) -> StrategySnapshot:
    active_jobs = await session.scalar(select(func.count(Job.id)).where(Job.is_active.is_(True)))
    total_companies = await session.scalar(select(func.count(CompanySnapshot.id)))
    return build_strategy_snapshot(
        active_jobs=active_jobs or 0,
        total_companies=total_companies or 0,
    )
