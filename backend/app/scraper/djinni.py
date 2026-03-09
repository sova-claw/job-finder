from __future__ import annotations

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.scraper.common import (
    collect_listing_payloads,
    parse_posted_at,
    render_html,
    save_scraped_posting,
)

DJINNI_URL = "https://djinni.co/jobs/?primary_keyword=Python&keywords=AI"


async def scrape_djinni(session: AsyncSession) -> dict[str, int]:
    html = await render_html(DJINNI_URL, "li[data-job-id], .list-jobs__item, .job-list-item")
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li[data-job-id], .list-jobs__item, .job-list-item")

    listings: list[tuple[str, str, str, object]] = []
    for card in cards[:60]:
        link = card.select_one("a.job-list-item__link, a.profile, a")
        if link is None or not link.get("href"):
            continue
        href = link["href"]
        url = href if href.startswith("http") else f"https://djinni.co{href}"
        title = link.get_text(" ", strip=True) or "Unknown role"
        company_node = card.select_one(
            ".mr-2.text-body-secondary, .text-body-secondary, .job-list-item__company"
        )
        company = company_node.get_text(" ", strip=True) if company_node else "Djinni"
        date_node = card.select_one("time, .text-body-secondary:last-child")
        posted_at = parse_posted_at(date_node.get_text(" ", strip=True) if date_node else None)
        listings.append((url, title, company, posted_at))

    postings = await collect_listing_payloads(listings, source="Djinni", source_group="Ukraine")

    created = 0
    skipped = 0
    for posting in postings:
        _job, is_new = await save_scraped_posting(session, posting)
        if is_new:
            created += 1
        else:
            skipped += 1

    await session.commit()
    return {
        "source": "Djinni",
        "count_found": len(listings),
        "count_new": created,
        "count_skipped": skipped,
    }
