from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.scraper.common import (
    collect_listing_payloads,
    dedupe_listings,
    fetch_html,
    parse_posted_at,
    save_scraped_posting,
)

logger = logging.getLogger(__name__)

COMPANIES = {
    "Grammarly": "https://www.grammarly.com/jobs",
    "Preply": "https://preply.com/en/jobs",
    "Restream": "https://restream.io/careers",
    "MacPaw": "https://macpaw.com/careers",
    "BetterMe": "https://betterme.world/careers",
    "Ajax Systems": "https://ajax.systems/careers",
    "Revolut": "https://www.revolut.com/careers/",
    "Wise": "https://wise.jobs/",
}


async def scrape_bigco(session: AsyncSession) -> dict[str, int]:
    found = 0
    created = 0
    skipped = 0

    for company, url in COMPANIES.items():
        try:
            html = await fetch_html(url)
        except httpx.HTTPError as exc:
            logger.warning(
                "BigCo source fetch failed",
                extra={"company": company, "error": str(exc)},
            )
            continue
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select(
            "a[href*='job'], a[href*='career'], a[href*='position'], a[href*='vacan']"
        )
        listings: list[tuple[str, str, str, datetime | None]] = []
        for link in links[:10]:
            href = link.get("href")
            if not href:
                continue
            job_url = urljoin(url, href)
            title = link.get_text(" ", strip=True) or f"{company} role"
            container_text = link.parent.get_text(" ", strip=True) if link.parent else ""
            posted_at = parse_posted_at(container_text)
            listings.append((job_url, title, company, posted_at))

        listings = dedupe_listings(listings)
        postings = await collect_listing_payloads(listings, source=company, source_group="BigCo")
        found += len(listings)
        for posting in postings:
            _job, is_new = await save_scraped_posting(session, posting)
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
