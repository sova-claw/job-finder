from __future__ import annotations

import re

from app.models.job import Job

PRIORITY_CHANNEL = "#jobs-priority"
ISRAEL_CHANNEL = "#jobs-israel"
UK_CHANNEL = "#jobs-uk"
POLAND_CHANNEL = "#jobs-poland"
REMOTE_EMEA_CHANNEL = "#jobs-remote-emea"

SOURCE_CHANNELS = {
    "careers_pages": "#src-careers-pages",
    "dou": "#src-dou",
    "djinni": "#src-djinni",
    "linkedin": "#src-linkedin",
    "hn": "#src-hn-hiring",
    "workatastartup": "#src-workatastartup",
}


def detect_country_channel(location: str | None) -> str:
    normalized = (location or "").strip().lower()
    israel_tokens = ("israel", "tel aviv", "jerusalem", "haifa")
    if any(token in normalized for token in israel_tokens) or re.search(r"\bil\b", normalized):
        return ISRAEL_CHANNEL
    uk_tokens = ("united kingdom", "london", "england", "scotland", "wales")
    if any(token in normalized for token in uk_tokens) or re.search(r"\buk\b", normalized):
        return UK_CHANNEL
    if any(token in normalized for token in ("poland", "krakow", "warsaw", "wroclaw", "gdansk")):
        return POLAND_CHANNEL
    return REMOTE_EMEA_CHANNEL


def source_channel_for_job(job: Job) -> str:
    source = (job.source or "").strip().lower()
    source_group = (job.source_group or "").strip().lower()

    if "dou" in source:
        return SOURCE_CHANNELS["dou"]
    if "djinni" in source:
        return SOURCE_CHANNELS["djinni"]
    if "linkedin" in source:
        return SOURCE_CHANNELS["linkedin"]
    if "hacker news" in source or source == "hn":
        return SOURCE_CHANNELS["hn"]
    if "workatastartup" in source or "work at a startup" in source:
        return SOURCE_CHANNELS["workatastartup"]
    if source_group == "startups":
        return SOURCE_CHANNELS["workatastartup"]
    return SOURCE_CHANNELS["careers_pages"]


def route_channels_for_job(job: Job) -> list[str]:
    if job.dealbreaker:
        return []

    score = job.match_score or 0
    if score >= 85:
        return [PRIORITY_CHANNEL, detect_country_channel(job.location)]
    if score >= 75:
        return [detect_country_channel(job.location)]
    return [source_channel_for_job(job)]
