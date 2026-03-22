from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import APIModel
from app.schemas.job import JobSummary

Track = Literal["sdet_qa", "ai_engineering"]


class CompanySummary(APIModel):
    id: str
    airtable_record_id: str
    name: str
    country: str | None = None
    city: str | None = None
    geo_bucket: str | None = None
    track_fit_sdet: bool
    track_fit_ai: bool
    brand_tier: str | None = None
    salary_hypothesis: str | None = None
    careers_url: str | None = None
    linkedin_url: str | None = None
    priority: str | None = None
    status: str | None = None
    notes: str | None = None
    openings_count: int = Field(default=0, ge=0)
    priority_score: int = Field(default=0, ge=0)
    recommended_action: str
    last_synced_at: datetime | None = None
    updated_at: datetime | None = None


class CompanyDetail(CompanySummary):
    related_jobs: list[JobSummary] = Field(default_factory=list)


class CompanyListResponse(BaseModel):
    items: list[CompanySummary]
    total: int


class AirtableSyncResponse(BaseModel):
    source: str = "Airtable"
    count_found: int
    count_created: int
    count_updated: int
    count_skipped: int
    synced_at: datetime
