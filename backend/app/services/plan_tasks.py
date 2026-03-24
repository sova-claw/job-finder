from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan_task import PlanTask
from app.schemas.plan_task import PlanTaskResponse
from app.services.slack import SlackPlanUpdateSummary, post_plan_update


def normalize_plan_title(title: str) -> str:
    words = " ".join(title.strip().split())
    if not words:
        raise ValueError("Task title is required")
    if len(words) <= 72:
        return words
    return words[:71].rstrip() + "…"


async def save_plan_task(
    session: AsyncSession,
    *,
    title: str,
    status: str,
    story_points: int | None = None,
    message: str | None = None,
    link: str | None = None,
    next_step: str | None = None,
) -> PlanTask:
    normalized_title = normalize_plan_title(title)
    normalized_status = status.strip().lower()

    result = await session.execute(
        select(PlanTask)
        .where(
            func.lower(PlanTask.title) == normalized_title.lower(),
            PlanTask.completed_at.is_(None),
        )
        .order_by(PlanTask.updated_at.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()

    if task is None:
        task = PlanTask(
            id=str(uuid4()),
            title=normalized_title,
            status=normalized_status,
        )
        session.add(task)

    task.status = normalized_status
    if story_points is not None:
        task.story_points = story_points
    task.message = message.strip() if message and message.strip() else None
    if link is not None:
        task.link = link.strip() if link and link.strip() else None
    if next_step is not None:
        task.next_step = next_step.strip() if next_step and next_step.strip() else None
    task.completed_at = (
        datetime.now(UTC) if normalized_status == "done" else None
    )

    await session.commit()
    await session.refresh(task)
    return task


async def attach_plan_task_slack_post(
    session: AsyncSession,
    *,
    task_id: str,
    thread_ts: str,
    post_ts: str,
) -> PlanTask:
    task = await session.get(PlanTask, task_id)
    if task is None:
        raise LookupError("Plan task not found")

    task.slack_thread_ts = thread_ts
    task.slack_last_post_ts = post_ts
    await session.commit()
    await session.refresh(task)
    return task


async def start_plan_task_from_selection(
    session: AsyncSession,
    *,
    title: str,
    story_points: int | None = None,
    default_thread_ts: str | None = None,
) -> SlackPlanUpdateSummary:
    normalized_title = normalize_plan_title(title)
    started_message = f"Started: {normalized_title}."
    started_next_step = f"First update on {normalized_title} will land here."
    task = await save_plan_task(
        session,
        title=normalized_title,
        status="started",
        story_points=story_points,
        message=started_message,
        next_step=started_next_step,
    )
    summary = await post_plan_update(
        status="started",
        title=task.title,
        message=started_message,
        story_points=story_points,
        next_step=started_next_step,
        task_id=task.id,
        thread_ts=task.slack_thread_ts or default_thread_ts,
    )
    await attach_plan_task_slack_post(
        session,
        task_id=task.id,
        thread_ts=summary.thread_ts or "",
        post_ts=summary.post_ts or "",
    )
    return summary


async def list_plan_tasks(
    session: AsyncSession,
    *,
    limit: int = 30,
) -> list[PlanTaskResponse]:
    result = await session.execute(
        select(PlanTask).order_by(PlanTask.updated_at.desc()).limit(limit)
    )
    return [PlanTaskResponse.model_validate(item) for item in result.scalars().all()]
