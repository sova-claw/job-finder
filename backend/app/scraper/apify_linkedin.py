from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.scraper.common import ScrapedPosting, save_scraped_posting

settings = get_settings()


async def scrape_apify_linkedin(session: AsyncSession) -> dict[str, int]:
    if not settings.apify_token:
        return {"source": "LinkedIn", "count_found": 0, "count_new": 0, "count_skipped": 0}

    url = "https://api.apify.com/v2/acts/followthesun~linkedin-jobs-scraper/run-sync-get-dataset-items"
    payload = {
        "keywords": ["Python AI Engineer", "ML Engineer", "AI Platform Engineer"],
        "location": "Remote",
        "rows": 20,
    }
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(
            f"{url}?token={settings.apify_token}",
            json=payload,
        )
        response.raise_for_status()
    items = response.json()

    found = 0
    created = 0
    skipped = 0
    for item in items:
        raw_text = item.get("descriptionText") or item.get("description") or ""
        posting = ScrapedPosting(
            url=item.get("jobUrl") or item.get("link") or "https://www.linkedin.com/jobs/",
            source="LinkedIn",
            source_group="Global",
            title=item.get("title") or "LinkedIn role",
            company=item.get("companyName") or "LinkedIn",
            posted_at=datetime.now(UTC),
            raw_text=raw_text,
        )
        _job, is_new = await save_scraped_posting(session, posting)
        found += 1
        if is_new:
            created += 1
        else:
            skipped += 1

    await session.commit()
    return {
        "source": "LinkedIn",
        "count_found": found,
        "count_new": created,
        "count_skipped": skipped,
    }
