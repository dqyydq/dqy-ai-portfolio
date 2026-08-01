from redis.asyncio import Redis

from app.core.config import get_settings

def create_redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def check_redis(redis_client: Redis) -> bool:
    try:
        return bool(await redis_client.ping())
    except Exception:
        return False
