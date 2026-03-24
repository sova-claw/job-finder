from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.alerts import (
    ScraperScheduleSnapshotResponse,
    SlackDispatchResponse,
    SlackInboxSnapshotResponse,
    SlackPlanUpdateRequest,
    SlackPlanUpdateResponse,
)
from app.scraper.scheduler import scheduler_service
from app.services.slack import (
    dispatch_new_jobs_to_slack,
    post_jobs_inbox_snapshot,
    post_plan_update,
)

router = APIRouter(tags=["alerts"])


@router.post("/alerts/slack/send", response_model=SlackDispatchResponse)
async def send_slack_alerts(session: AsyncSession = Depends(get_session)) -> SlackDispatchResponse:
    try:
        summary = await dispatch_new_jobs_to_slack(session)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return SlackDispatchResponse(
        count_found=summary.count_found,
        count_posted=summary.count_posted,
        count_skipped=summary.count_skipped,
        dispatched_at=summary.dispatched_at,
    )


@router.post("/alerts/slack/inbox", response_model=SlackInboxSnapshotResponse)
async def send_slack_inbox_snapshot(
    session: AsyncSession = Depends(get_session),
) -> SlackInboxSnapshotResponse:
    try:
        summary = await post_jobs_inbox_snapshot(session)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return SlackInboxSnapshotResponse(
        channel=summary.channel,
        count_rows=summary.count_rows,
        posted_at=summary.posted_at,
    )


@router.post("/alerts/slack/scraper-schedule", response_model=ScraperScheduleSnapshotResponse)
async def send_scraper_schedule_snapshot() -> ScraperScheduleSnapshotResponse:
    try:
        summary = await scheduler_service.post_schedule_snapshot()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scraper scheduler snapshot could not be posted",
        )

    return ScraperScheduleSnapshotResponse(
        channel=summary.channel,
        count_jobs=summary.count_jobs,
        posted_at=summary.posted_at,
    )


@router.post("/alerts/slack/plans", response_model=SlackPlanUpdateResponse)
async def send_plan_update(payload: SlackPlanUpdateRequest) -> SlackPlanUpdateResponse:
    try:
        summary = await post_plan_update(
            status=payload.status,
            message=payload.message,
            next_step=payload.next_step,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return SlackPlanUpdateResponse(
        channel=summary.channel,
        status=summary.status,
        posted_at=summary.posted_at,
    )
