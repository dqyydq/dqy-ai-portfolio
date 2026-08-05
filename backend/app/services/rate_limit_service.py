from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis

RATE_LIMIT_PREFIX = "agent:rate-limit:message"
RATE_LIMIT_VERSION = "v1"
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60

FIXED_WINDOW_SCRIPT = """
local count = redis.call("INCR", KEYS[1])

if count == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end

local ttl = redis.call("TTL", KEYS[1])
return {count, ttl}
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


def build_rate_limit_key(user_id: UUID) -> str:
    return f"{RATE_LIMIT_PREFIX}:{RATE_LIMIT_VERSION}:{user_id}"


async def check_message_rate_limit(
    redis_client: Redis,
    user_id: UUID,
) -> RateLimitResult:
    key = build_rate_limit_key(user_id)

    raw_count, raw_ttl = await redis_client.eval(
        FIXED_WINDOW_SCRIPT,
        1,
        key,
        RATE_LIMIT_WINDOW_SECONDS,
    )
    count = int(raw_count)
    ttl = max(int(raw_ttl), 0)

    return RateLimitResult(
        allowed=count <= RATE_LIMIT_MAX_REQUESTS,
        limit=RATE_LIMIT_MAX_REQUESTS,
        remaining=max(RATE_LIMIT_MAX_REQUESTS - count, 0),
        retry_after=ttl,
    )