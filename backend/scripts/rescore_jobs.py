from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.job import Job
from app.services.extractor import extract_job_details
from app.services.profile import (
    get_candidate_profile,
    matches_abroad_remote_preference,
    matches_focus_role,
)
from app.services.scorer import score_job


async def main() -> None:
    profile = get_candidate_profile()
    async with SessionLocal() as session:
        result = await session.execute(select(Job))
        jobs = result.scalars().all()

        for job in jobs:
            extraction = await extract_job_details(
                job.raw_text or "",
                url=job.url,
                source=job.source,
            )
            score, gaps = score_job(extraction, profile)
            job.title = extraction.title
            job.company = extraction.company
            job.company_type = extraction.company_type
            job.salary_min = extraction.salary_min
            job.salary_max = extraction.salary_max
            job.requirements_must = extraction.requirements_must
            job.requirements_nice = extraction.requirements_nice
            job.tags = extraction.tags
            job.domain = extraction.domain
            job.remote = extraction.remote
            job.location = extraction.location
            job.match_score = score
            job.gaps = [gap.model_dump() for gap in gaps]
            job.is_active = matches_focus_role(extraction.title, job.raw_text or "") and (
                matches_abroad_remote_preference(
                    title=extraction.title,
                    location=extraction.location,
                    raw_text=job.raw_text or "",
                    remote=extraction.remote,
                )
            )

        await session.commit()
        print(f"rescored_jobs={len(jobs)}")


if __name__ == "__main__":
    asyncio.run(main())
