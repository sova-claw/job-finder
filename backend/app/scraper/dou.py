from __future__ import annotations

from datetime import UTC, datetime

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.scraper.common import ScrapedPosting, fetch_html, fetch_text, save_scraped_posting

DOU_URL = "https://jobs.dou.ua/vacancies/?category=AI%2FML"


async def scrape_dou(session: AsyncSession) -> dict[str, int]:
    html = await fetch_html(DOU_URL)
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li.l-vacancy, div.vacancy")

    found = 0
    created = 0
    skipped = 0
    for card in cards[:60]:
        link = card.select_one("a.vt, a.job-link, a")
        if link is None or not link.get("href"):
            continue
        found += 1
        url = link["href"]
        raw_text = await fetch_text(url)
        title = link.get_text(" ", strip=True) or "Unknown role"
        company_node = card.select_one(".company, .company a, .title")
        company = company_node.get_text(" ", strip=True) if company_node else "DOU"
        posting = ScrapedPosting(
            url=url,
            source="DOU",
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
    return {"source": "DOU", "count_found": found, "count_new": created, "count_skipped": skipped}
