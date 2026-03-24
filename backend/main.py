import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.routers import (
    alerts_router,
    analysis_router,
    companies_router,
    job_chat_router,
    jobs_router,
    research_router,
    stats_router,
    strategy_router,
)
from app.scraper.scheduler import scheduler_service

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    scheduler_service.start()
    try:
        await scheduler_service.post_schedule_snapshot()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to post scraper scheduler snapshot on startup: %s", exc)
    try:
        yield
    finally:
        scheduler_service.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router, prefix=settings.api_prefix)
app.include_router(analysis_router, prefix=settings.api_prefix)
app.include_router(stats_router, prefix=settings.api_prefix)
app.include_router(alerts_router, prefix=settings.api_prefix)
app.include_router(companies_router, prefix=settings.api_prefix)
app.include_router(job_chat_router, prefix=settings.api_prefix)
app.include_router(research_router, prefix=settings.api_prefix)
app.include_router(strategy_router, prefix=settings.api_prefix)


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}
