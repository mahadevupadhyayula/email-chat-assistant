from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.health import HealthResponse
from app.services.health import check_database

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_db)) -> HealthResponse:  # noqa: B008
    if await check_database(session):
        return HealthResponse(status="ok", database="ok")
    return HealthResponse(status="degraded", database="unreachable")
