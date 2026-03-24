from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.scraper.common import ScrapedPosting, parse_posted_at, save_scraped_posting


def resolve_external_djinni_repo_path() -> Path:
    settings = get_settings()
    configured = Path(settings.external_djinni_repo_path)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[3] / configured


def djinni_start_urls() -> list[str]:
    settings = get_settings()
    return [
        item.strip()
        for item in settings.external_djinni_start_urls_csv.split(",")
        if item.strip()
    ]


async def _run_external_djinni_cli() -> list[dict[str, object]]:
    settings = get_settings()
    repo_path = resolve_external_djinni_repo_path()
    if not repo_path.exists():
        raise RuntimeError(f"External Djinni scraper repo not found: {repo_path}")

    command = [
        "uv",
        "run",
        "python",
        "-m",
        "scraper_djinni_market_data.cli",
        "--max-pages",
        str(settings.external_djinni_max_pages),
        "--format",
        "json",
    ]
    for start_url in djinni_start_urls():
        command.extend(["--start-url", start_url])
    if settings.external_djinni_max_items is not None:
        command.extend(["--max-items", str(settings.external_djinni_max_items)])
    if settings.djinni_cookie_header.strip():
        command.extend(["--cookie-header", settings.djinni_cookie_header.strip()])

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(repo_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            "External Djinni scraper failed: "
            + (stderr.decode("utf-8", errors="replace").strip() or "unknown error")
        )
    return json.loads(stdout.decode("utf-8"))


def _posting_from_row(row: dict[str, object]) -> ScrapedPosting:
    url = str(row.get("listing_url") or "").strip()
    title = str(row.get("title") or "Unknown role").strip() or "Unknown role"
    company = str(row.get("company") or "Djinni").strip() or "Djinni"
    posted_at = parse_posted_at(str(row.get("posted_at") or "").strip() or None)
    description_text = str(row.get("description_text") or "").strip()
    salary_raw = str(row.get("salary_raw") or "").strip()
    raw_text = description_text or salary_raw or title
    return ScrapedPosting(
        url=url,
        source="Djinni",
        source_group="Ukraine",
        title=title,
        company=company,
        posted_at=posted_at,
        raw_text=raw_text,
    )


async def scrape_external_djinni(session: AsyncSession) -> dict[str, object]:
    rows = await _run_external_djinni_cli()
    created = 0
    skipped = 0
    for row in rows:
        _job, is_new = await save_scraped_posting(session, _posting_from_row(row))
        if is_new:
            created += 1
        else:
            skipped += 1

    await session.commit()
    return {
        "source": "Djinni",
        "count_found": len(rows),
        "count_new": created,
        "count_skipped": skipped,
    }
