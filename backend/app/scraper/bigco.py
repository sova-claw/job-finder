from __future__ import annotations

from datetime import UTC, datetime

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.scraper.common import ScrapedPosting, fetch_html, fetch_text, save_scraped_posting

COMPANIES = {
    "Grammarly": "https://www.grammarly.com/jobs",
    "Preply": "https://preply.com/en/jobs",
    "Restream": "https://restream.io/careers",
    "Revolut": "https://www.revolut.com/careers/",
    "Wise": "https://wise.jobs/",
}


async def scrape_bigco(session: AsyncSession) -> dict[str, int]:
    found = 0
    created = 0
    skipped = 0

    for company, url in COMPANIES.items():
        html = await fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select("a[href*='job'], a[href*='career'], a[href*='open-position']")
        for link in links[:10]:
            href = link.get("href")
            if not href:
                continue
            job_url = href if href.startswith("http") else f"{url.rstrip('/')}/{href.lstrip('/')}"
            raw_text = await fetch_text(job_url)
            title = link.get_text(" ", strip=True) or f"{company} role"
            posting = ScrapedPosting(
                url=job_url,
                source=company,
                source_group="BigCo",
                title=title,
                company=company,
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
        "source": "BigCo",
        "count_found": found,
        "count_new": created,
        "count_skipped": skipped,
    }
