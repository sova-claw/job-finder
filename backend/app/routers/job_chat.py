from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.job_chat import (
    CreateJobChatMessageRequest,
    JobChatMessageResponse,
    JobChatResponse,
)
from app.services.job_chat import create_job_chat_message, list_job_chat

router = APIRouter(prefix="/jobs", tags=["job-chat"])


@router.get("/{job_id}/chat", response_model=JobChatResponse)
async def get_job_chat(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> JobChatResponse:
    try:
        items = await list_job_chat(session, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return JobChatResponse(items=items, total=len(items))


@router.post(
    "/{job_id}/chat",
    response_model=JobChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_job_chat(
    job_id: str,
    payload: CreateJobChatMessageRequest,
    session: AsyncSession = Depends(get_session),
) -> JobChatMessageResponse:
    try:
        return await create_job_chat_message(session, job_id=job_id, payload=payload)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
