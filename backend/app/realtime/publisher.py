import json
from uuid import UUID

from redis.asyncio import Redis

from app.realtime.events import RealtimeEvent


REALTIME_USER_CHANNEL_PREFIX = "agent:realtime:user"
REALTIME_EVENT_VERSION = "v1"


def build_user_realtime_channel(user_id: UUID) -> str:
    return (
        f"{REALTIME_USER_CHANNEL_PREFIX}:"
        f"{REALTIME_EVENT_VERSION}:{user_id}"
    )


async def publish_user_realtime_event(
    redis_client: Redis,
    user_id: UUID,
    event: RealtimeEvent,
) -> None:
    await redis_client.publish(
        build_user_realtime_channel(user_id),
        json.dumps(event.to_payload()),
    )