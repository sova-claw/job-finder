# Scraper Strategy

## Current source plan

Local scrapers:
- DOU via Playwright-rendered listings and direct detail-page fetches
- Djinni via Playwright-rendered listings and direct detail-page fetches
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
