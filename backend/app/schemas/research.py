from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import APIModel


class ResearchEvidence(APIModel):
    url: str
    title: str | None = None
    source_domain: str | None = None
    snippet: str | None = None


class ResearchFindingResponse(APIModel):
    id: str
    job_id: str | None = None
    company_snapshot_id: str | None = None
    finding_type: str
    title: str
    summary: str
    confidence: int | None = Field(default=None, ge=0, le=100)
    tags: list[str] | None = None
    evidence: list[ResearchEvidence] | None = None
    source_kind: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateResearchFindingRequest(BaseModel):
    finding_type: str = Field(default="company_signal", min_length=2, max_length=80)
    title: str = Field(min_length=2, max_length=180)
    summary: str = Field(min_length=4, max_length=4000)
    confidence: int | None = Field(default=None, ge=0, le=100)
    tags: list[str] | None = None
    source_kind: str = Field(default="manual", min_length=2, max_length=40)
    created_by: str = Field(default="Nazar", min_length=1, max_length=80)
    evidence: list[ResearchEvidence] | None = None
    source_url: str | None = None
    source_title: str | None = None
    source_domain: str | None = None
    source_snippet: str | None = None


class ResearchFindingListResponse(BaseModel):
    items: list[ResearchFindingResponse]
    total: int
