import json
import os
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slack_sdk.signature import SignatureVerifier
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
from app.services.plan_tasks import (
    attach_plan_task_slack_post,
    save_plan_task,
    start_plan_task_from_selection,
)
from app.services.slack import (
    dispatch_new_jobs_to_slack,
    post_jobs_inbox_snapshot,
    post_plan_update,
)

router = APIRouter(tags=["alerts"])


def _verify_slack_request(request: Request, body: bytes) -> None:
    signing_secret = os.getenv("SLACK_SIGNING_SECRET", "").strip()
    if not signing_secret:
        return

    verifier = SignatureVerifier(signing_secret=signing_secret)
    if not verifier.is_valid_request(body=body, headers=request.headers):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack signature",
        )


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
async def send_plan_update(
    payload: SlackPlanUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> SlackPlanUpdateResponse:
    try:
        task = await save_plan_task(
            session,
            title=payload.title,
            status=payload.status,
            story_points=payload.story_points,
            message=payload.message,
            link=payload.link,
            next_step=payload.next_step,
        )
        summary = await post_plan_update(
            status=payload.status,
            title=task.title,
            message=payload.message,
            story_points=payload.story_points,
            next_step=payload.next_step,
            link=payload.link,
            task_id=task.id,
            thread_ts=task.slack_thread_ts,
        )
        await attach_plan_task_slack_post(
            session,
            task_id=task.id,
            thread_ts=summary.thread_ts or "",
            post_ts=summary.post_ts or "",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return SlackPlanUpdateResponse(
        channel=summary.channel,
        status=summary.status,
        task_id=summary.task_id,
        posted_at=summary.posted_at,
    )


@router.post("/alerts/slack/interactivity")
async def handle_slack_interactivity(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Response:
    body = await request.body()
    _verify_slack_request(request, body)

    payload_raw = parse_qs(body.decode("utf-8")).get("payload", [None])[0]
    if not payload_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Slack payload",
        )

    payload = json.loads(payload_raw)
    action = (payload.get("actions") or [{}])[0]
    if not str(action.get("action_id", "")).startswith("plan_pick_task"):
        return Response(status_code=status.HTTP_200_OK)

    value = json.loads(action.get("value", "{}"))
    title = str(value.get("title", "")).strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Task title is required",
        )

    story_points_raw = value.get("story_points")
    story_points = int(story_points_raw) if story_points_raw is not None else None

    try:
        await start_plan_task_from_selection(
            session,
            title=title,
            story_points=story_points,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_200_OK)
