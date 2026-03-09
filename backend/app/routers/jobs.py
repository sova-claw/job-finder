from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.job import Job
from app.schemas.job import AnalyzeUrlRequest, JobDetail, JobListResponse
from app.services.ingest import to_job_detail, to_job_summary, upsert_job_from_url
from app.services.search import build_job_query

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
async def list_jobs(
    source_group: str | None = Query(default=None),
    sort_by: str = Query(default="match_score"),
    sort_dir: str = Query(default="desc"),
    search: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> JobListResponse:
    query = build_job_query(
        source_group=source_group,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    result = await session.execute(query)
    jobs = result.scalars().all()
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    return JobListResponse(items=[to_job_summary(job) for job in jobs], total=total or 0)


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> JobDetail:
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return to_job_detail(job)


@router.post("/analyze-url", response_model=JobDetail, status_code=status.HTTP_201_CREATED)
async def analyze_url(
    payload: AnalyzeUrlRequest,
    session: AsyncSession = Depends(get_session),
) -> JobDetail:
    job = await upsert_job_from_url(session, str(payload.url))
    return to_job_detail(job)
