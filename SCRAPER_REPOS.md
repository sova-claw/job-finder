# Scraper Repos

The scraper family is split into separate repos so each scraper can be reused privately,
shipped on Apify, or monetized on its own.

## Repo family
- local: `../scraper-core`
- remote: `git@github.com:sova-claw/scraper-core.git`
- local: `../scraper-djinni-market-data`
- remote: `git@github.com:sova-claw/scraper-djinni-market-data.git`
- later: `../scraper-dou-market-data`, `../scraper-startupindex`, etc.

## job_finder integration
- `job_finder` consumes product repos via git submodules under `external/scrapers/`
- current first integration: `external/scrapers/scraper-djinni-market-data`
- the adapter contract is CLI-first: the external repo emits flat JSON rows, `job_finder` ingests them

## Current state
- internal Djinni scraper stays as the default path
- set `EXTERNAL_DJINNI_SCRAPER_ENABLED=true` to switch to the external repo
- external config:
  - `EXTERNAL_DJINNI_REPO_PATH`
  - `EXTERNAL_DJINNI_START_URLS_CSV`
  - `EXTERNAL_DJINNI_MAX_PAGES`
  - `EXTERNAL_DJINNI_MAX_ITEMS`
