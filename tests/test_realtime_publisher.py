import asyncio
import json
from uuid import uuid4

from app.db.redis import create_redis_client
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import (
    build_user_realtime_channel,
    publish_user_realtime_event,
)


async def _read_published_message(pubsub):
    for _ in range(20):
        message = await pubsub.get_message(
            ignore_subscribe_messages=True,
            timeout=0.1,
        )
        if message is not None:
            return message
        await asyncio.sleep(0.01)
    return None


async def test_user_event_is_published_to_its_own_channel() -> None:
    user_id = uuid4()
    subscriber = create_redis_client()
    publisher = create_redis_client()
    pubsub = subscriber.pubsub()

    try:
        await pubsub.subscribe(build_user_realtime_channel(user_id))
        await publish_user_realtime_event(
            redis_client=publisher,
            user_id=user_id,
            event=RealtimeEvent(
                type=RealtimeEventType.REVIEW_COMPLETED,
                task_id=uuid4(),
                data={"status": "completed"},
            ),
        )

        message = await _read_published_message(pubsub)
        assert message is not None
        payload = json.loads(message["data"])
        assert payload["type"] == "review.completed"
        assert payload["data"] == {"status": "completed"}
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()
        await subscriber.aclose()
        await publisher.aclose()
