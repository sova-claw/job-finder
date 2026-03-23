from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.job_chat import JobChatMessage
from app.schemas.job_chat import CreateJobChatMessageRequest, JobChatMessageResponse


async def ensure_job(session: AsyncSession, job_id: str) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise LookupError("Job not found")
    return job


async def list_job_chat(session: AsyncSession, job_id: str) -> list[JobChatMessageResponse]:
    await ensure_job(session, job_id)
    result = await session.execute(
        select(JobChatMessage)
        .where(JobChatMessage.job_id == job_id)
        .order_by(JobChatMessage.created_at.asc())
    )
    return [JobChatMessageResponse.model_validate(item) for item in result.scalars().all()]


async def create_job_chat_message(
    session: AsyncSession,
    *,
    job_id: str,
    payload: CreateJobChatMessageRequest,
) -> JobChatMessageResponse:
    await ensure_job(session, job_id)
    message = JobChatMessage(
        id=str(uuid4()),
        job_id=job_id,
        role=payload.role,
        author=payload.author.strip(),
        content=payload.content.strip(),
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return JobChatMessageResponse.model_validate(message)
