from fastapi import APIRouter, HTTPException, status

from app.db.database import check_database
from app.db.redis import check_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> dict[str, str]:
    database_ok, redis_ok = await check_database(), await check_redis()
    if not (database_ok and redis_ok):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"database": database_ok, "redis": redis_ok},
        )
    return {"status": "ready", "database": "ok", "redis": "ok"}

