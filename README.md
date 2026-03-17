# Career Intelligence System

Career Intelligence System is a self-hosted job intelligence dashboard for Python QA automation and SDET roles.

## Stack

- Backend: Python 3.12, `uv`, FastAPI, SQLAlchemy async, Alembic, APScheduler
- Frontend: Next.js 15, TypeScript strict, Tailwind CSS v4, TanStack Query v5, Recharts
- Database: PostgreSQL 17 with `pgvector`
- Infra: Docker Compose, Caddy

## Sources

- Local scrapers: DOU, Djinni, BigCo, Hacker News
- Hosted scraper: LinkedIn via Apify
- Scraper plan and source notes: `SCRAPERS.md`

## Local backend workflow

```bash
cd backend
uv sync --dev
uv run alembic upgrade head
uv run uvicorn main:app --reload
```

## Local frontend workflow

```bash
cd frontend
npm install
npm run dev
```

## Verification

```bash
cd backend && uv run ruff check . && uv run pytest
cd frontend && npm run build
```

## Docker

```bash
docker compose up -d
curl http://localhost:8000/health
```

Expected health response:

```json
{"status":"ok","db":"connected"}
```

## Refresh local data

```bash
cd backend
uv run python scripts/rescore_jobs.py
```
