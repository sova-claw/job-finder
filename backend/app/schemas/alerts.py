from datetime import datetime

from pydantic import BaseModel, Field


class SlackDispatchResponse(BaseModel):
    source: str = "Slack"
    count_found: int
    count_posted: int
    count_skipped: int
    dispatched_at: datetime


class SlackInboxSnapshotResponse(BaseModel):
    source: str = "Slack Inbox"
    channel: str
    count_rows: int
    posted_at: datetime


class ScraperScheduleSnapshotResponse(BaseModel):
    source: str = "Scraper Scheduler"
    channel: str
    count_jobs: int
    posted_at: datetime


class SlackPlanUpdateRequest(BaseModel):
    status: str = Field(min_length=2, max_length=20)
    title: str = Field(min_length=2, max_length=72)
    message: str = Field(min_length=2, max_length=300)
    story_points: int | None = Field(default=None, ge=1, le=13)
    next_step: str | None = Field(default=None, max_length=300)
    link: str | None = Field(default=None, max_length=500)


class SlackPlanUpdateResponse(BaseModel):
    source: str = "Slack Plans"
    channel: str
    status: str
    task_id: str | None = None
    posted_at: datetime
