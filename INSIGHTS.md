# INSIGHTS

## 2026-03-09
- Selected `uv` instead of Poetry per direct user request.
- Kept schema/indexes aligned with requirements Section 8.
- Added Dockerized startup path that migrates DB before starting FastAPI.
- Implemented deterministic extraction, scoring, and cover-letter fallbacks so the app remains useful without AI keys.
- Kept ingestion unified: manual URL analysis and scheduled scrapers both flow through the same job enrichment pipeline.
- Switched the frontend from a placeholder container to a real Next.js 15 dashboard with typed API integration and an actionable detail panel.
- Locked Docker dependency installs against `uv.lock` and `package-lock.json` for reproducible builds.
- Replaced DOU and Djinni list capture with Playwright-rendered HTML and added parsed posted-date handling for more stable dedup.
- Moved stats away from full-table ORM loads, added DB-side search-vector maintenance, and tightened Anthropic prompt parsing/logging.
