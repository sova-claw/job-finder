from __future__ import annotations

from app.models.job import Job

PRIORITY_CHANNEL = "#jobs-priority"
INBOX_CHANNEL = "#jobs-inbox"


def route_channels_for_job(job: Job) -> list[str]:
    if job.dealbreaker:
        return []

    score = job.match_score or 0
    if score >= 75:
        return [PRIORITY_CHANNEL]
    return [INBOX_CHANNEL]
