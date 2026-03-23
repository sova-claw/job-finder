from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.research import (
    CreateResearchFindingRequest,
    ResearchFindingListResponse,
    ResearchFindingResponse,
)
from app.services.research import create_job_research, list_company_research, list_job_research

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/jobs/{job_id}", response_model=ResearchFindingListResponse)
async def get_job_research(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> ResearchFindingListResponse:
    try:
        items = await list_job_research(session, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ResearchFindingListResponse(items=items, total=len(items))


@router.post(
    "/jobs/{job_id}",
    response_model=ResearchFindingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_job_research(
    job_id: str,
    payload: CreateResearchFindingRequest,
    session: AsyncSession = Depends(get_session),
) -> ResearchFindingResponse:
    try:
        return await create_job_research(session, job_id=job_id, payload=payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/companies/{company_id}", response_model=ResearchFindingListResponse)
async def get_company_research(
    company_id: str,
    session: AsyncSession = Depends(get_session),
) -> ResearchFindingListResponse:
    try:
        items = await list_company_research(session, company_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ResearchFindingListResponse(items=items, total=len(items))
