from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.plan_task import PlanTaskListResponse
from app.services.plan_tasks import list_plan_tasks

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/tasks", response_model=PlanTaskListResponse)
async def get_plan_tasks(
    session: AsyncSession = Depends(get_session),
) -> PlanTaskListResponse:
    items = await list_plan_tasks(session)
    return PlanTaskListResponse(items=items, total=len(items))
