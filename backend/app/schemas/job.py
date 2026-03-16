from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.common import APIModel

SourceGroup = Literal["Ukraine", "BigCo", "Startups", "Global"]
Verdict = Literal["apply_now", "prepare_first", "not_aligned"]


class Gap(BaseModel):
    skill: str
    current: int = Field(ge=0, le=100)
    target: int = Field(default=100, ge=0, le=100)
    weeks_to_close: int = Field(ge=0)


class JobExtraction(BaseModel):
    title: str
    company: str
    company_type: Literal["Product", "Service", "Startup", "Unknown"]
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    requirements_must: list[str] = Field(default_factory=list)
    requirements_nice: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, max_length=10)
    domain: str
    remote: bool
    location: str | None = None


class JobSummary(APIModel):
    id: str
    url: str
    source: str
    source_group: SourceGroup
    title: str | None = None
    company: str | None = None
    company_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    tags: list[str] | None = None
    domain: str | None = None
    remote: bool | None = None
    location: str | None = None
    match_score: int | None = None
    top_gap: str | None = None
    verdict: Verdict = "not_aligned"
    posted_at: datetime | None = None
    scraped_at: datetime | None = None
    is_active: bool


class JobDetail(JobSummary):
    raw_text: str | None = None
    requirements_must: list[str] | None = None
    requirements_nice: list[str] | None = None
    gaps: list[Gap] | None = None
    extracted_at: datetime | None = None


class AnalyzeUrlRequest(BaseModel):
    url: HttpUrl


class JobListResponse(BaseModel):
    items: list[JobSummary]
    total: int


class JobStats(BaseModel):
    total_jobs: int
    active_jobs: int
    avg_score: float
    high_pay_count: int
    top_gap: str | None = None
    source_breakdown: dict[str, int]


class SkillCount(BaseModel):
    skill: str
    count: int


class SalaryBandCount(BaseModel):
    band: str
    count: int


class MarketInsight(BaseModel):
    top_skills: list[SkillCount]
    salary_distribution: list[SalaryBandCount]
    remote_ratio: float
