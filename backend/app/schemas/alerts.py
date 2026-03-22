from datetime import datetime

from pydantic import BaseModel


class SlackDispatchResponse(BaseModel):
    source: str = "Slack"
    count_found: int
    count_posted: int
    count_skipped: int
    dispatched_at: datetime
