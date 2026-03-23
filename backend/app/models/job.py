from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_group: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)

    title: Mapped[str | None] = mapped_column(Text)
    company: Mapped[str | None] = mapped_column(Text)
    company_type: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    requirements_must: Mapped[list[str] | None] = mapped_column(JSONB)
    requirements_nice: Mapped[list[str] | None] = mapped_column(JSONB)
    tags: Mapped[list[str] | None] = mapped_column(JSONB)
    domain: Mapped[str | None] = mapped_column(Text)
    remote: Mapped[bool | None] = mapped_column(Boolean)
    location: Mapped[str | None] = mapped_column(Text)

    match_score: Mapped[int | None] = mapped_column(Integer)
    gaps: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    hard_matches: Mapped[list[str] | None] = mapped_column(JSONB)
    soft_matches: Mapped[list[str] | None] = mapped_column(JSONB)
    dealbreaker: Mapped[bool | None] = mapped_column(Boolean)

    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    slack_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    slack_channel_id: Mapped[str | None] = mapped_column(Text)
    slack_channel_name: Mapped[str | None] = mapped_column(Text)
    slack_channel_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
