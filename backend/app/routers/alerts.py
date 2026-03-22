from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.alerts import SlackDispatchResponse
from app.services.slack import dispatch_new_jobs_to_slack

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
