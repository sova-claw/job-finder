# Scraper Strategy

## Current source plan

Local scrapers:
- DOU via Playwright-rendered listings and direct detail-page fetches
- Djinni via direct HTML fetches and JSON-LD parsing
- BigCo career pages via direct HTML fetches
- Hacker News Who's Hiring via thread comment scraping

Hosted scraper:
- LinkedIn via Apify actor execution

Disabled by default:
- YC / Work at a Startup via Apify is intentionally not scheduled

## Why this split

- DOU and Djinni are niche regional sources and are better controlled locally.
- BigCo pages are custom enough that a lightweight local fetch is still cheaper than a third-party actor.
- LinkedIn is the source most likely to break under local scraping, so using Apify there gives the best time savings.
- HN is simple enough to keep fully local.

## Current role focus

- Candidate target: `Python QA Automation Engineer / SDET`
- DOU query: `category=QA&search=python automation`
- Djinni query: `primary_keyword=QA Automation&keywords=Python`
- LinkedIn Apify titles: `Senior QA Automation Engineer`, `QA Automation Engineer`, `Python QA Engineer`, `SDET`, `Test Automation Engineer`
- Relevance gate: only jobs with both QA automation role signal and Python/testing stack signal remain active

## Reliability priorities

1. DOU
2. Djinni
3. LinkedIn (Apify)
4. BigCo
5. HN

## Immediate hardening done

- Deduplicate listing URLs before detail fetches.
- Parse ISO dates in addition to relative timestamps.
- Use comment-anchor URLs for HN so each post is stored separately.
- Switch LinkedIn to the official Apify Python client with configurable actor inputs.
- Keep Apify usage limited to LinkedIn only.

## Next improvements

1. Add scrape run persistence (`scrape_runs` table with counts and errors).
2. Add a manual `/api/admin/scrape` trigger for personal-use refreshes.
3. Improve BigCo company-specific selectors to reduce noisy links.
4. Add Playwright browser/session reuse for DOU and Djinni list rendering.
5. Add source-level integration tests using recorded fixtures.
