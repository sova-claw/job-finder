from __future__ import annotations

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.scraper.common import (
    collect_listing_payloads,
    parse_posted_at,
    render_html,
    save_scraped_posting,
)

DOU_URL = "https://jobs.dou.ua/vacancies/?category=AI%2FML"


async def scrape_dou(session: AsyncSession) -> dict[str, int]:
    html = await render_html(DOU_URL, "li.l-vacancy, div.vacancy")
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li.l-vacancy, div.vacancy")

    listings: list[tuple[str, str, str, object]] = []
    for card in cards[:60]:
        link = card.select_one("a.vt, a.job-link, a")
        if link is None or not link.get("href"):
            continue
        url = link["href"]
        title = link.get_text(" ", strip=True) or "Unknown role"
        company_node = card.select_one(".company, .company a, .title")
        company = company_node.get_text(" ", strip=True) if company_node else "DOU"
        date_node = card.select_one(".date, .publ-date, .vacancy-date")
        posted_at = parse_posted_at(date_node.get_text(" ", strip=True) if date_node else None)
        listings.append((url, title, company, posted_at))

    postings = await collect_listing_payloads(listings, source="DOU", source_group="Ukraine")

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
        "source": "DOU",
        "count_found": len(listings),
        "count_new": created,
        "count_skipped": skipped,
    }
