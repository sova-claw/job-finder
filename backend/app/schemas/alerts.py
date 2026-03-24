from datetime import datetime

from pydantic import BaseModel


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
