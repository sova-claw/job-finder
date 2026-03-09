from __future__ import annotations

from datetime import UTC, datetime

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.scraper.common import ScrapedPosting, fetch_html, fetch_text, save_scraped_posting

DJINNI_URL = "https://djinni.co/jobs/?primary_keyword=Python&keywords=AI"


async def scrape_djinni(session: AsyncSession) -> dict[str, int]:
    html = await fetch_html(DJINNI_URL)
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li[data-job-id], .list-jobs__item, .job-list-item")

    found = 0
    created = 0
    skipped = 0
    for card in cards[:60]:
        link = card.select_one("a.job-list-item__link, a.profile, a")
        if link is None or not link.get("href"):
            continue
        found += 1
        href = link["href"]
        url = href if href.startswith("http") else f"https://djinni.co{href}"
        raw_text = await fetch_text(url)
        title = link.get_text(" ", strip=True) or "Unknown role"
        company_node = card.select_one(
            ".mr-2.text-body-secondary, .text-body-secondary, .job-list-item__company"
        )
        company = company_node.get_text(" ", strip=True) if company_node else "Djinni"
        posting = ScrapedPosting(
            url=url,
            source="Djinni",
            source_group="Ukraine",
            title=title,
            company=company,
            posted_at=datetime.now(UTC),
            raw_text=raw_text,
        )
        _job, is_new = await save_scraped_posting(session, posting)
        if is_new:
            created += 1
        else:
            skipped += 1

    await session.commit()
    return {
        "source": "Djinni",
        "count_found": found,
        "count_new": created,
        "count_skipped": skipped,
    }
