from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.job import Job
from app.schemas.cover_letter import CoverLetterRequest, CoverLetterResponse
from app.services.cover_letter import generate_cover_letter

router = APIRouter(prefix="/jobs", tags=["analysis"])


@router.post("/{job_id}/cover-letter", response_model=CoverLetterResponse)
async def create_cover_letter(
    job_id: str,
    payload: CoverLetterRequest,
    session: AsyncSession = Depends(get_session),
) -> CoverLetterResponse:
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return await generate_cover_letter(session, job, payload.tone)
