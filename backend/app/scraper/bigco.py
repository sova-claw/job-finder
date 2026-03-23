from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import CompanySnapshot
from app.scraper.common import (
    collect_listing_payloads,
    dedupe_listings,
    fetch_html,
    parse_posted_at,
    render_html,
    render_text,
    save_scraped_posting,
)
from app.services.profile import has_role_focus_signal, matches_focus_role

logger = logging.getLogger(__name__)
GENERIC_LINK_SELECTOR = "a[href*='job'], a[href*='career'], a[href*='position'], a[href*='vacan']"
WIX_LINK_SELECTOR = "a[href*='/position/']"
PLAYWRIGHT_REQUIRED = {"Wix"}

COMPANIES_UA = {
    "Grammarly": "https://www.grammarly.com/jobs",
    "Preply": "https://preply.com/en/jobs",
    "Restream": "https://restream.io/careers",
    "MacPaw": "https://macpaw.com/careers",
    "BetterMe": "https://betterme.world/careers",
    "Ajax Systems": "https://ajax.systems/careers",
    "Revolut": "https://www.revolut.com/careers/",
    "Wise": "https://wise.jobs/",
}

COMPANIES_TARGET = {
    "JFrog": "https://jfrog.com/careers/",
    "Tipalti": "https://tipalti.com/careers/",
    "monday.com": "https://monday.com/jobs/",
    # Wix renders jobs behind a JS-only careers app, so use the canonical positions page.
    "Wix": "https://careers.wix.com/positions",
    "Forter": "https://forter.com/careers/",
    "Paddle": "https://paddle.com/careers/",
    "Sentry": "https://sentry.io/careers/",
    "Mercury": "https://mercury.com/jobs",
    "Rapyd": "https://www.rapyd.net/company/careers/",
    "Brex": "https://www.brex.com/careers",
}


def _build_company_targets(companies: list[CompanySnapshot]) -> dict[str, str]:
    targets: dict[str, str] = {}

    for company in sorted(companies, key=lambda item: item.name.lower()):
        if not company.careers_url or not (company.track_fit_sdet or company.track_fit_ai):
            continue
        targets[company.name] = company.careers_url

    for company, url in COMPANIES_TARGET.items():
        targets.setdefault(company, url)

    return targets


async def _load_company_targets(session: AsyncSession) -> dict[str, str]:
    result = await session.execute(select(CompanySnapshot))
    return _build_company_targets(list(result.scalars().all()))


async def _fetch_with_playwright(url: str) -> str:
    return await render_html(url, WIX_LINK_SELECTOR)


async def _fetch_wix_text(url: str) -> str:
    return await render_text(url, "h1")


def _parse_wix_listings(
    html: str,
    *,
    company: str,
    base_url: str,
) -> list[tuple[str, str, str, datetime | None]]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[tuple[str, str, str, datetime | None]] = []

    for link in soup.select(WIX_LINK_SELECTOR):
        href = link.get("href")
        if not href:
            continue

        container = link.find_parent("div", attrs={"role": "listitem"})
        if container is None:
            continue

        title_node = container.find(attrs={"data-testid": "richTextElement"})
        title = title_node.get_text(" ", strip=True) if title_node is not None else ""
        container_text = container.get_text(" ", strip=True)
        if not title or title.lower() in {"browse positions", "no results found"}:
            title = container_text.replace("Browse positions", "").strip()
        if not has_role_focus_signal(f"{title}\n{container_text}"):
            continue

        listings.append(
            (urljoin(base_url, href), title, company, parse_posted_at(container_text))
        )

    return dedupe_listings(listings)[:10]


async def scrape_bigco(session: AsyncSession) -> dict[str, int]:
    found = 0
    created = 0
    skipped = 0

    company_targets = await _load_company_targets(session)

    for company, url in company_targets.items():
        try:
            html = (
                await _fetch_with_playwright(url)
                if company in PLAYWRIGHT_REQUIRED
                else await fetch_html(url)
            )
        except (httpx.HTTPError, PlaywrightError) as exc:
            logger.warning(
                "BigCo source fetch failed",
                extra={"company": company, "error": str(exc)},
            )
            continue
        if company in PLAYWRIGHT_REQUIRED:
            listings = _parse_wix_listings(html, company=company, base_url=url)
            postings = await collect_listing_payloads(
                listings,
                source=company,
                source_group="BigCo",
                fetch_text_fn=_fetch_wix_text,
            )
        else:
            soup = BeautifulSoup(html, "html.parser")
            links = soup.select(GENERIC_LINK_SELECTOR)
            listings: list[tuple[str, str, str, datetime | None]] = []
            for link in links[:10]:
                href = link.get("href")
                if not href:
                    continue
                job_url = urljoin(url, href)
                title = link.get_text(" ", strip=True) or f"{company} role"
                container_text = link.parent.get_text(" ", strip=True) if link.parent else ""
                if not has_role_focus_signal(f"{title}\n{container_text}"):
                    continue
                posted_at = parse_posted_at(container_text)
                listings.append((job_url, title, company, posted_at))

            listings = dedupe_listings(listings)
            postings = await collect_listing_payloads(
                listings,
                source=company,
                source_group="BigCo",
            )
        postings = [
            posting
            for posting in postings
            if matches_focus_role(posting.title, posting.raw_text)
        ]
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
