from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import APIModel

ChatRole = Literal["user", "assistant", "system"]


class JobChatMessageResponse(APIModel):
    id: str
    job_id: str
    role: ChatRole
    author: str | None = None
    content: str
    created_at: datetime | None = None


class CreateJobChatMessageRequest(BaseModel):
    role: ChatRole = "user"
    author: str = Field(default="Nazar", min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=6000)


class JobChatResponse(BaseModel):
    items: list[JobChatMessageResponse]
    total: int
