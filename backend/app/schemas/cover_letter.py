from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Tone = Literal["professional", "direct", "enthusiastic"]


class CoverLetterRequest(BaseModel):
    tone: Tone = "professional"


class CoverLetterResponse(BaseModel):
    id: str
    job_id: str
    tone: Tone
    letter: str
    profile_tags_used: list[str]
    cached: bool
    created_at: datetime | None = None
