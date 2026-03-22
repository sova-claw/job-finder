from app.routers.alerts import router as alerts_router
from app.routers.analysis import router as analysis_router
from app.routers.companies import router as companies_router
from app.routers.jobs import router as jobs_router
from app.routers.stats import router as stats_router
from app.routers.strategy import router as strategy_router

__all__ = [
    "alerts_router",
    "analysis_router",
    "companies_router",
    "jobs_router",
    "stats_router",
    "strategy_router",
]
