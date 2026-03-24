from __future__ import annotations

import json

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.scraper.common import (
    collect_listing_payloads,
    dedupe_listings,
    fetch_html,
    parse_posted_at,
    save_scraped_posting,
)
from app.services.external_djinni_adapter import scrape_external_djinni
from app.services.profile import matches_focus_role

DJINNI_URL = "https://djinni.co/jobs/?primary_keyword=QA%20Automation&keywords=Python"


def parse_jobposting_scripts(html: str) -> list[tuple[str, str, str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[tuple[str, str, str, object]] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw_payload = script.string or script.get_text(strip=True)
        if not raw_payload:
            continue

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            continue

        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                continue

            url = item.get("url")
            title = item.get("title")
            if not url or not title:
                continue

            organization = item.get("hiringOrganization") or {}
            company = organization.get("name") if isinstance(organization, dict) else None
            posted_at = parse_posted_at(item.get("datePosted"))
            listings.append((url, title, company or "Djinni", posted_at))

    return dedupe_listings(listings)


async def scrape_djinni(session: AsyncSession) -> dict[str, int]:
    if get_settings().external_djinni_scraper_enabled:
        return await scrape_external_djinni(session)

    html = await fetch_html(DJINNI_URL)
    listings = parse_jobposting_scripts(html)

    if not listings:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("li[data-job-id], .list-jobs__item, .job-list-item")

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

        listings = dedupe_listings(listings)

    postings = await collect_listing_payloads(listings, source="Djinni", source_group="Ukraine")
    postings = [
        posting
        for posting in postings
        if matches_focus_role(posting.title, posting.raw_text)
    ]

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
