from app.schemas.cover_letter import CoverLetterRequest, CoverLetterResponse
from app.schemas.job import (
    AnalyzeUrlRequest,
    Gap,
    JobDetail,
    JobExtraction,
    JobListResponse,
    JobStats,
    JobSummary,
    MarketInsight,
)
from app.schemas.profile import CandidateProfile

__all__ = [
    "AnalyzeUrlRequest",
    "CandidateProfile",
    "CoverLetterRequest",
    "CoverLetterResponse",
    "Gap",
    "JobDetail",
    "JobExtraction",
    "JobListResponse",
    "MarketInsight",
    "JobStats",
    "JobSummary",
]
