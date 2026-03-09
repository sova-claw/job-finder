from app.routers.analysis import router as analysis_router
from app.routers.jobs import router as jobs_router
from app.routers.stats import router as stats_router

__all__ = ["analysis_router", "jobs_router", "stats_router"]
