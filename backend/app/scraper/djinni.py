from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal, cast

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
DjinniScraperMode = Literal["internal", "external-local", "canary"]


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


async def scrape_djinni(session: AsyncSession) -> dict[str, object]:
    mode = resolve_djinni_scraper_mode()
    if mode == "external-local":
        return await scrape_external_djinni(session)
    if mode == "canary":
        return await scrape_djinni_canary(session)

    return await _scrape_internal_djinni(session)


def resolve_djinni_scraper_mode(*, now: datetime | None = None) -> DjinniScraperMode:
    settings = get_settings()
    configured = settings.djinni_scraper_mode.strip().lower()
    mode: DjinniScraperMode
    if configured in {"internal", "external-local", "canary"}:
        mode = cast(DjinniScraperMode, configured)
    else:
        mode = "external-local" if settings.external_djinni_scraper_enabled else "internal"

    if mode != "canary":
        return mode

    if settings.djinni_canary_until is None:
        return "canary"

    reference_time = (now or datetime.now(UTC)).astimezone(UTC)
    canary_until = settings.djinni_canary_until.astimezone(UTC)
    if reference_time >= canary_until:
        return "internal"
    return "canary"


async def scrape_djinni_canary(session: AsyncSession) -> dict[str, object]:
    primary = await scrape_external_djinni(session)
    details = [
        "Mode: canary · external-local primary",
    ]

    try:
        shadow = await _scrape_internal_djinni(session, persist=False)
        shadow_candidates = int(shadow.get("count_candidates", 0))
        shadow_found = int(shadow.get("count_found", 0))
        primary_found = int(primary.get("count_found", 0))
        details.append(
            "Shadow internal: "
            f"{shadow_candidates} matched / {shadow_found} found"
        )
        found_delta = primary_found - shadow_found
        if found_delta:
            details.append(f"Found delta: {found_delta:+d}")
    except Exception as exc:  # noqa: BLE001
        details.append(f"Shadow internal failed: {exc}")

    return {
        **primary,
        "details": details,
    }


async def _scrape_internal_djinni(
    session: AsyncSession,
    *,
    persist: bool = True,
) -> dict[str, object]:
    listings = await _load_djinni_listings()
    postings = await collect_listing_payloads(listings, source="Djinni", source_group="Ukraine")
    postings = [
        posting
        for posting in postings
        if matches_focus_role(posting.title, posting.raw_text)
    ]

    if not persist:
        return {
            "source": "Djinni",
            "count_found": len(listings),
            "count_candidates": len(postings),
            "count_new": 0,
            "count_skipped": 0,
        }

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


async def _load_djinni_listings() -> list[tuple[str, str, str, object]]:
    html = await fetch_html(DJINNI_URL)
    listings = parse_jobposting_scripts(html)

    if listings:
        return listings

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

    return dedupe_listings(listings)
