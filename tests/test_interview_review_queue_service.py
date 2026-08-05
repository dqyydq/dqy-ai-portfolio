from uuid import uuid4

from app.db.redis import create_redis_client
from app.services.interview_review_queue_service import (
    INTERVIEW_REVIEW_STREAM,
    publish_interview_review_task,
)


async def test_publish_interview_review_task_adds_task_id_to_stream() -> None:
    redis_client = create_redis_client()
    task_id = uuid4()
    message_id = None

    try:
        message_id = await publish_interview_review_task(redis_client, task_id)

        entries = await redis_client.xrange(
            INTERVIEW_REVIEW_STREAM,
            min=message_id,
            max=message_id,
        )

        assert len(entries) == 1
        persisted_message_id, fields = entries[0]
        assert persisted_message_id == message_id
        assert fields == {"task_id": str(task_id)}
    finally:
        if message_id is not None:
            await redis_client.xdel(INTERVIEW_REVIEW_STREAM, message_id)
        await redis_client.aclose()
