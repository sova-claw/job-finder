from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.company import CompanySnapshot
from app.scraper.common import (
    ScrapedPosting,
    collect_listing_payloads,
    parse_posted_at,
    save_scraped_posting,
)
from app.services.profile import has_role_focus_signal, matches_focus_role

settings = get_settings()
logger = logging.getLogger(__name__)

GENERIC_LINK_SELECTOR = "a[href*='job'], a[href*='career'], a[href*='position'], a[href*='vacan']"
ASHBY_APP_DATA_PATTERN = re.compile(r"window\.__appData\s*=\s*(\{.*?\});", re.DOTALL)
GREENHOUSE_TOKEN_PATTERN = re.compile(
    r"(?:boards\.greenhouse\.io/embed/job_board\?for=|job-boards\.greenhouse\.io/)"
    r"([a-z0-9_-]+)",
    re.IGNORECASE,
)
LEVER_SITE_PATTERN = re.compile(r"https://jobs\.lever\.co/([a-z0-9_-]+)", re.IGNORECASE)

AtsKind = Literal["greenhouse", "lever", "ashby", "generic"]


@dataclass(slots=True)
class CareerTarget:
    company: str
    url: str


@dataclass(slots=True)
class CareerListing:
    url: str
    title: str
    company: str
    posted_at: datetime | None = None
    raw_text: str | None = None


@dataclass(slots=True)
class FetchedPage:
    requested_url: str
    final_url: str
    html: str


def load_targets_from_csv(path: str | Path) -> list[CareerTarget]:
    csv_path = Path(path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        targets: list[CareerTarget] = []
        for row in reader:
            company = (row.get("company") or row.get("name") or "").strip()
            url = (row.get("url") or row.get("careers_url") or "").strip()
            if not company or not url:
                continue
            targets.append(CareerTarget(company=company, url=_normalize_url(url)))
    return _dedupe_targets(targets)


async def load_targets_from_company_snapshots(session: AsyncSession) -> list[CareerTarget]:
    result = await session.execute(
        select(CompanySnapshot.name, CompanySnapshot.careers_url).where(
            CompanySnapshot.careers_url.is_not(None)
        )
    )
    targets = [
        CareerTarget(company=name, url=_normalize_url(url))
        for name, url in result.all()
        if name and url
    ]
    return _dedupe_targets(targets)


def detect_ats(page: FetchedPage) -> AtsKind:
    lowered_url = page.final_url.lower()
    lowered_html = page.html.lower()
    if "greenhouse" in lowered_url or "greenhouse" in lowered_html:
        return "greenhouse"
    if "jobs.lever.co" in lowered_url or "api.lever.co" in lowered_html:
        return "lever"
    if "ashbyhq.com" in lowered_url or "window.__appdata" in lowered_html:
        return "ashby"
    return "generic"


def parse_greenhouse_jobs(payload: dict[str, Any], company: str) -> list[CareerListing]:
    listings: list[CareerListing] = []
    for job in payload.get("jobs", []):
        if not isinstance(job, dict):
            continue
        title = str(job.get("title") or "").strip()
        url = str(job.get("absolute_url") or "").strip()
        if not title or not url:
            continue

        location = ""
        raw_location = job.get("location")
        if isinstance(raw_location, dict):
            location = str(raw_location.get("name") or "").strip()

        if not has_role_focus_signal("\n".join(filter(None, (title, location)))):
            continue

        listings.append(
            CareerListing(
                url=url,
                title=title,
                company=company,
                posted_at=parse_posted_at(
                    str(job.get("first_published") or job.get("updated_at") or "").strip()
                ),
            )
        )
    return _dedupe_listings(listings)


def parse_lever_jobs(payload: list[dict[str, Any]], company: str) -> list[CareerListing]:
    listings: list[CareerListing] = []
    for job in payload:
        if not isinstance(job, dict):
            continue
        title = str(job.get("text") or "").strip()
        url = str(job.get("hostedUrl") or job.get("applyUrl") or "").strip()
        if not title or not url:
            continue

        categories = job.get("categories")
        location = ""
        team = ""
        commitment = ""
        if isinstance(categories, dict):
            location = str(categories.get("location") or "").strip()
            team = str(categories.get("team") or categories.get("department") or "").strip()
            commitment = str(categories.get("commitment") or "").strip()

        description_plain = str(job.get("descriptionPlain") or "").strip()
        if not description_plain:
            description_html = str(job.get("description") or "").strip()
            if description_html:
                description_plain = BeautifulSoup(description_html, "html.parser").get_text(
                    "\n", strip=True
                )

        searchable_text = "\n".join(filter(None, (title, location, team, description_plain)))
        if not has_role_focus_signal(searchable_text):
            continue

        listings.append(
            CareerListing(
                url=url,
                title=title,
                company=company,
                posted_at=parse_posted_at(str(job.get("createdAt") or job.get("updatedAt") or "")),
                raw_text="\n".join(
                    filter(None, (title, company, location, team, commitment, description_plain))
                ),
            )
        )
    return _dedupe_listings(listings)


def parse_ashby_jobs(html: str, company: str, base_url: str) -> list[CareerListing]:
    match = ASHBY_APP_DATA_PATTERN.search(html)
    if match is None:
        return []

    app_data = json.loads(match.group(1))
    app_company = (
        app_data.get("organization", {}).get("name")
        if isinstance(app_data.get("organization"), dict)
        else None
    )
    postings = (
        app_data.get("jobBoard", {}).get("jobPostings", [])
        if isinstance(app_data.get("jobBoard"), dict)
        else []
    )

    listings: list[CareerListing] = []
    for job in postings:
        if not isinstance(job, dict) or not job.get("isListed", True):
            continue
        title = str(job.get("title") or "").strip()
        if not title:
            continue

        location_parts: list[str] = []
        primary_location = str(job.get("locationName") or "").strip()
        if primary_location:
            location_parts.append(primary_location)
        for location in job.get("secondaryLocations", []):
            if not isinstance(location, dict):
                continue
            name = str(location.get("locationName") or "").strip()
            if name and name not in location_parts:
                location_parts.append(name)

        team = str(job.get("teamName") or job.get("departmentName") or "").strip()
        workplace_type = str(job.get("workplaceType") or "").strip()
        searchable_text = "\n".join(filter(None, (title, team, *location_parts)))
        if not has_role_focus_signal(searchable_text):
            continue

        location_text = " | ".join(location_parts)
        listings.append(
            CareerListing(
                url=_build_ashby_job_url(base_url, job),
                title=title,
                company=app_company or company,
                posted_at=parse_posted_at(
                    str(job.get("publishedDate") or job.get("updatedAt") or "").strip()
                ),
                raw_text="\n".join(
                    filter(
                        None,
                        (
                            title,
                            app_company or company,
                            team,
                            location_text,
                            workplace_type,
                            str(job.get("employmentType") or "").strip(),
                            str(job.get("compensationTierSummary") or "").strip(),
                        ),
                    )
                ),
            )
        )
    return _dedupe_listings(listings)


def parse_generic_careers_html(html: str, company: str, base_url: str) -> list[CareerListing]:
    soup = BeautifulSoup(html, "html.parser")
    listings: list[CareerListing] = []

    for link in soup.select(GENERIC_LINK_SELECTOR):
        href = link.get("href")
        if not href:
            continue
        title = link.get_text(" ", strip=True)
        context = link.parent.get_text(" ", strip=True) if link.parent else title
        if not title or not has_role_focus_signal("\n".join((title, context))):
            continue
        listings.append(
            CareerListing(
                url=urljoin(base_url, href),
                title=title,
                company=company,
                posted_at=parse_posted_at(context),
            )
        )
    return _dedupe_listings(listings)


async def scrape_careers_pages(
    session: AsyncSession,
    *,
    csv_path: str | Path | None = None,
    targets: list[CareerTarget] | None = None,
) -> dict[str, int]:
    active_targets = await _resolve_targets(session, csv_path=csv_path, targets=targets)
    if not active_targets:
        logger.info("No careers-page targets available")
        return {
            "source": "CareersPage",
            "count_found": 0,
            "count_new": 0,
            "count_skipped": 0,
            "count_failed": 0,
        }

    found = 0
    created = 0
    skipped = 0
    failed = 0

    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": settings.scraper_user_agent},
    ) as client:
        for target in active_targets:
            try:
                listings = await _scrape_target(client, target)
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                failed += 1
                logger.warning(
                    "Careers-page scrape failed",
                    extra={"company": target.company, "url": target.url, "error": str(exc)},
                )
                continue

            found += len(listings)
            postings = await _build_postings_for_target(target, listings)
            for posting in postings:
                _job, is_new = await save_scraped_posting(session, posting)
                if is_new:
                    created += 1
                else:
                    skipped += 1

    await session.commit()
    return {
        "source": "CareersPage",
        "count_found": found,
        "count_new": created,
        "count_skipped": skipped,
        "count_failed": failed,
    }


async def _resolve_targets(
    session: AsyncSession,
    *,
    csv_path: str | Path | None,
    targets: list[CareerTarget] | None,
) -> list[CareerTarget]:
    if targets:
        return _dedupe_targets(targets)
    if csv_path is not None and Path(csv_path).exists():
        return load_targets_from_csv(csv_path)
    return await load_targets_from_company_snapshots(session)


async def _scrape_target(client: httpx.AsyncClient, target: CareerTarget) -> list[CareerListing]:
    page = await _resolve_target_page(client, target)
    if page is None:
        raise ValueError(f"No reachable careers page found for {target.company}")

    ats = detect_ats(page)
    if ats == "greenhouse":
        payload = await _fetch_json(client, _build_greenhouse_feed_url(page))
        if not isinstance(payload, dict):
            raise ValueError("Greenhouse feed returned unexpected payload")
        return parse_greenhouse_jobs(payload, target.company)
    if ats == "lever":
        payload = await _fetch_json(client, _build_lever_feed_url(page))
        if not isinstance(payload, list):
            raise ValueError("Lever feed returned unexpected payload")
        return parse_lever_jobs(payload, target.company)
    if ats == "ashby":
        return parse_ashby_jobs(page.html, target.company, page.final_url)
    return parse_generic_careers_html(page.html, target.company, page.final_url)


async def _build_postings_for_target(
    target: CareerTarget, listings: list[CareerListing]
) -> list[ScrapedPosting]:
    listings = _dedupe_listings(listings)
    direct_postings = [
        ScrapedPosting(
            url=listing.url,
            source=target.company,
            source_group="BigCo",
            title=listing.title,
            company=listing.company,
            posted_at=listing.posted_at,
            raw_text=listing.raw_text,
        )
        for listing in listings
        if listing.raw_text
    ]

    fetched_postings: list[ScrapedPosting] = []
    pending_listings = [
        (listing.url, listing.title, listing.company, listing.posted_at)
        for listing in listings
        if listing.raw_text is None
    ]
    if pending_listings:
        fetched_postings = await collect_listing_payloads(
            pending_listings,
            source=target.company,
            source_group="BigCo",
        )

    return [
        posting
        for posting in direct_postings + fetched_postings
        if matches_focus_role(posting.title, posting.raw_text)
    ]


async def _resolve_target_page(
    client: httpx.AsyncClient, target: CareerTarget
) -> FetchedPage | None:
    for url in _candidate_urls(target.url):
        try:
            response = await client.get(url)
            if response.status_code >= 400:
                continue
            return FetchedPage(requested_url=url, final_url=str(response.url), html=response.text)
        except httpx.HTTPError:
            continue
    return None


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict[str, Any] | list[dict[str, Any]]:
    response = await client.get(url)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, (dict, list)):
        raise ValueError("Unexpected JSON payload")
    return payload


def _build_greenhouse_feed_url(page: FetchedPage) -> str:
    token = _extract_greenhouse_board_token(page)
    if not token:
        raise ValueError(f"Unable to infer Greenhouse board token from {page.final_url}")
    return f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def _build_lever_feed_url(page: FetchedPage) -> str:
    site = _extract_lever_site(page)
    if not site:
        raise ValueError(f"Unable to infer Lever site from {page.final_url}")
    return f"https://api.lever.co/v0/postings/{site}?mode=json"


def _extract_greenhouse_board_token(page: FetchedPage) -> str | None:
    parsed = urlsplit(page.final_url)
    query_token = parse_qs(parsed.query).get("for")
    if query_token:
        return query_token[0]

    if parsed.netloc in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments:
            return segments[0]

    match = GREENHOUSE_TOKEN_PATTERN.search(page.html)
    if match is not None:
        return match.group(1)
    return None


def _extract_lever_site(page: FetchedPage) -> str | None:
    parsed = urlsplit(page.final_url)
    if parsed.netloc == "jobs.lever.co":
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments:
            return segments[0]

    match = LEVER_SITE_PATTERN.search(page.html)
    if match is not None:
        return match.group(1)
    return None


def _normalize_url(url: str) -> str:
    return url if "://" in url else f"https://{url}"


def _candidate_urls(url: str) -> list[str]:
    normalized = _normalize_url(url)
    parsed = urlsplit(normalized)
    clean_path = parsed.path.rstrip("/")
    base = urlunsplit((parsed.scheme, parsed.netloc, clean_path or "/", "", ""))

    if clean_path and clean_path not in {"", "/"}:
        return [base]
    candidates = [
        urljoin(base, "/careers"),
        urljoin(base, "/jobs"),
        urljoin(base, "/careers/"),
        urljoin(base, "/jobs/"),
        base,
    ]
    return list(dict.fromkeys(candidates))


def _build_ashby_job_url(base_url: str, job: dict[str, Any]) -> str:
    parsed = urlsplit(base_url)
    job_id = str(job.get("jobId") or job.get("id") or "").strip()
    if not job_id:
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
    query = urlencode({"jobId": job_id})
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def _dedupe_targets(targets: list[CareerTarget]) -> list[CareerTarget]:
    seen: set[tuple[str, str]] = set()
    deduped: list[CareerTarget] = []
    for target in targets:
        key = (target.company.lower(), target.url.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)
    return deduped


def _dedupe_listings(listings: list[CareerListing]) -> list[CareerListing]:
    seen_urls: set[str] = set()
    deduped: list[CareerListing] = []
    for listing in listings:
        if listing.url in seen_urls:
            continue
        seen_urls.add(listing.url)
        deduped.append(listing)
    return deduped
