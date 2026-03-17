from __future__ import annotations

import logging
from typing import Any

from apify_client import ApifyClientAsync
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.scraper.common import (
    ScrapedPosting,
    parse_posted_at,
    save_scraped_posting,
    split_csv,
)
from app.services.profile import matches_focus_role

settings = get_settings()
logger = logging.getLogger(__name__)


def build_linkedin_run_inputs(
    *,
    titles_csv: str,
    location: str,
    date_posted: str,
    limit_per_title: int,
    company_names_csv: str = "",
    contract_types_csv: str = "",
    experience_levels_csv: str = "",
    remote_codes_csv: str = "",
    skip_job_ids_csv: str = "",
) -> list[dict[str, Any]]:
    titles = split_csv(titles_csv)
    company_names = split_csv(company_names_csv)
    contract_types = split_csv(contract_types_csv)
    experience_levels = split_csv(experience_levels_csv)
    remote_codes = split_csv(remote_codes_csv)
    skip_job_ids = split_csv(skip_job_ids_csv)

    run_inputs: list[dict[str, Any]] = []
    for title in titles:
        payload: dict[str, Any] = {
            "title": title,
            "maxItems": limit_per_title,
        }
        if location:
            payload["location"] = location
        if date_posted:
            payload["datePosted"] = date_posted
        if company_names:
            payload["companyName"] = company_names
        if contract_types:
            payload["contractType"] = contract_types
        if experience_levels:
            payload["experienceLevel"] = experience_levels
        if remote_codes:
            payload["remote"] = remote_codes
        if skip_job_ids:
            payload["skipJobId"] = skip_job_ids
        run_inputs.append(payload)

    return run_inputs


def posting_from_linkedin_item(item: dict[str, Any]) -> ScrapedPosting | None:
    url = item.get("jobUrl") or item.get("url") or item.get("link")
    if not url:
        return None

    title = item.get("title") or item.get("position") or "LinkedIn role"
    raw_text = (
        item.get("descriptionText")
        or item.get("description")
        or item.get("jobDescription")
        or ""
    )
    if not matches_focus_role(title, raw_text):
        return None
    posted_at = parse_posted_at(item.get("postedDate") or item.get("postedTimeAgo"))
    return ScrapedPosting(
        url=url,
        source="LinkedIn",
        source_group="Global",
        title=title,
        company=item.get("companyName") or item.get("company") or "LinkedIn",
        posted_at=posted_at,
        raw_text=raw_text,
    )


async def iterate_actor_items(
    client: ApifyClientAsync,
    actor_id: str,
    run_input: dict[str, Any],
) -> list[dict[str, Any]]:
    run = await client.actor(actor_id).call(
        run_input=run_input,
        timeout_secs=settings.apify_actor_timeout_seconds,
        wait_secs=settings.apify_actor_timeout_seconds,
    )
    if not run or not run.get("defaultDatasetId"):
        logger.warning("LinkedIn Apify actor returned no dataset", extra={"actor_id": actor_id})
        return []

    dataset_client = client.dataset(run["defaultDatasetId"])
    return [item async for item in dataset_client.iterate_items(clean=True)]


async def scrape_apify_linkedin(session: AsyncSession) -> dict[str, int]:
    if not settings.apify_token:
        return {"source": "LinkedIn", "count_found": 0, "count_new": 0, "count_skipped": 0}

    run_inputs = build_linkedin_run_inputs(
        titles_csv=settings.apify_linkedin_titles_csv,
        location=settings.apify_linkedin_location,
        date_posted=settings.apify_linkedin_date_posted,
        limit_per_title=settings.apify_linkedin_limit_per_title,
        company_names_csv=settings.apify_linkedin_company_names_csv,
        contract_types_csv=settings.apify_linkedin_contract_types_csv,
        experience_levels_csv=settings.apify_linkedin_experience_levels_csv,
        remote_codes_csv=settings.apify_linkedin_remote_codes_csv,
        skip_job_ids_csv=settings.apify_linkedin_skip_job_ids_csv,
    )
    if not run_inputs:
        return {"source": "LinkedIn", "count_found": 0, "count_new": 0, "count_skipped": 0}

    client = ApifyClientAsync(settings.apify_token)
    found = 0
    created = 0
    skipped = 0
    seen_urls: set[str] = set()

    for run_input in run_inputs:
        items = await iterate_actor_items(client, settings.apify_linkedin_actor_id, run_input)
        found += len(items)
        for item in items:
            posting = posting_from_linkedin_item(item)
            if posting is None or posting.url in seen_urls:
                continue
            seen_urls.add(posting.url)
            _job, is_new = await save_scraped_posting(session, posting)
            if is_new:
                created += 1
            else:
                skipped += 1

    await session.commit()
    return {
        "source": "LinkedIn",
        "count_found": found,
        "count_new": created,
        "count_skipped": skipped,
    }
