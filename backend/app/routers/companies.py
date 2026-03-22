from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.company import AirtableSyncResponse, CompanyDetail, CompanyListResponse, Track
from app.services.company_sync import get_company_detail, list_companies, sync_airtable_companies

router = APIRouter(tags=["companies"])


@router.get("/companies", response_model=CompanyListResponse)
async def companies_list(
    track: Track | None = Query(default=None),
    country: str | None = Query(default=None),
    search: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> CompanyListResponse:
    items, total = await list_companies(session, track=track, country=country, search=search)
    return CompanyListResponse(items=items, total=total)


@router.get("/companies/{company_id}", response_model=CompanyDetail)
async def company_detail(
    company_id: str,
    session: AsyncSession = Depends(get_session),
) -> CompanyDetail:
    company = await get_company_detail(session, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.post("/sync/airtable", response_model=AirtableSyncResponse)
async def sync_airtable(session: AsyncSession = Depends(get_session)) -> AirtableSyncResponse:
    try:
        summary = await sync_airtable_companies(session)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return AirtableSyncResponse(
        count_found=summary.count_found,
        count_created=summary.count_created,
        count_updated=summary.count_updated,
        count_skipped=summary.count_skipped,
        synced_at=summary.synced_at,
    )
