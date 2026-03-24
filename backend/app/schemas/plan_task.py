from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import APIModel


class PlanTaskResponse(APIModel):
    id: str
    title: str
    status: str
    story_points: int | None = Field(default=None, ge=1, le=13)
    message: str | None = None
    link: str | None = None
    next_step: str | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PlanTaskListResponse(BaseModel):
    items: list[PlanTaskResponse]
    total: int
