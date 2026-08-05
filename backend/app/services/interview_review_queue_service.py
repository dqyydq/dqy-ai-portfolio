import uuid

from redis.asyncio import Redis

INTERVIEW_REVIEW_STREAM = "agent:queue:interview-review:v1"


async def publish_interview_review_task(
    redis_client: Redis,
    task_id: uuid.UUID,
) -> str:
    message_id = await redis_client.xadd(
        INTERVIEW_REVIEW_STREAM,
        {
            "task_id": str(task_id),
        },
    )
    return message_id