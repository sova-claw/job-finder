from __future__ import annotations

from datetime import UTC, datetime

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.scraper.common import ScrapedPosting, fetch_html, save_scraped_posting

settings = get_settings()


async def scrape_hn_jobs(session: AsyncSession) -> dict[str, int]:
    hn_url = f"https://news.ycombinator.com/item?id={settings.hn_thread_id}"
    html = await fetch_html(hn_url)
    soup = BeautifulSoup(html, "html.parser")
    comments = soup.select(".comment-tree .athing.comtr")

    found = 0
    created = 0
    skipped = 0
    for comment in comments[:40]:
        text_node = comment.select_one(".commtext")
        if text_node is None:
            continue
        raw_text = text_node.get_text("\n", strip=True)
        title = raw_text.split("\n", maxsplit=1)[0][:100]
        posting = ScrapedPosting(
            url=hn_url,
            source="HN",
            source_group="Startups",
            title=title or "HN role",
            company="HN Who's Hiring",
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
    return {"source": "HN", "count_found": found, "count_new": created, "count_skipped": skipped}
