from typing import Annotated

from fastapi import Depends, HTTPException, Response, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.api.deps import get_current_user, get_redis_client
from app.models.user import User
from app.services.rate_limit_service import (
    RateLimitResult,
    check_message_rate_limit,
)


async def enforce_message_rate_limit(
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> RateLimitResult:
    try:
        result = await check_message_rate_limit(
            redis_client=redis_client,
            user_id=current_user.id,
        )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limit service unavailable",
        ) from exc

    headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
    }

    if not result.allowed:
        headers["Retry-After"] = str(result.retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers=headers,
        )

    for name, value in headers.items():
        response.headers[name] = value

    return result