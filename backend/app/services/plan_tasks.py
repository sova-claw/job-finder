from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


def estimate_for_story_points(story_points: int | None) -> str | None:
    if story_points is None:
        return None
    mapping = {
        1: "~10 min",
        2: "~15 min",
        3: "~25 min",
        5: "~45 min",
    }
    return mapping.get(story_points, "~1h")


def estimate_finish_time(story_points: int | None) -> str | None:
    if story_points is None:
        return None
    minute_mapping = {
        1: 10,
        2: 15,
        3: 25,
        5: 45,
    }
    minutes = minute_mapping.get(story_points, 60)
    finish_at = datetime.now().astimezone() + timedelta(minutes=minutes)
    return f"Ends ~{finish_at.strftime('%H:%M')}"


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
    del default_thread_ts
    normalized_title = normalize_plan_title(title)
    estimate = estimate_for_story_points(story_points)
    eta_text = estimate_finish_time(story_points)
    progress_message = (
        f"In progress · est. {estimate}."
        if estimate
        else "In progress."
    )
    root_message = "Started from task list."
    root_next_step = "Use this thread for updates and questions."
    task = await save_plan_task(
        session,
        title=normalized_title,
        status="progress",
        story_points=story_points,
        message=progress_message,
        next_step=root_next_step,
    )
    root_summary = await post_plan_update(
        status="started",
        title=task.title,
        message=root_message,
        story_points=story_points,
        next_step=root_next_step,
        task_id=task.id,
        thread_ts=None,
    )
    summary = await post_plan_update(
        status="progress",
        title=task.title,
        message=progress_message,
        story_points=story_points,
        eta_text=eta_text,
        next_step=root_next_step,
        task_id=task.id,
        thread_ts=root_summary.thread_ts,
    )
    await attach_plan_task_slack_post(
        session,
        task_id=task.id,
        thread_ts=root_summary.thread_ts or "",
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
