from uuid import uuid4

from app.db.redis import create_redis_client
from app.workers.interview_review_worker import (
    ensure_consumer_group,
    run_worker_once,
)


class FakeLLMClient:
    async def generate(self, _prompt):
        return "## Summary\nUnused task"


async def test_worker_reads_one_new_stream_message_from_its_consumer_group() -> None:
    redis_client = create_redis_client()
    suffix = uuid4().hex
    stream_name = f"agent:test:interview-review:{suffix}"
    group_name = f"group-{suffix}"
    consumer_name = f"consumer-{suffix}"
    llm_client = FakeLLMClient()

    try:
        await ensure_consumer_group(redis_client, stream_name, group_name)
        await redis_client.xadd(stream_name, {"task_id": str(uuid4())})

        assert await run_worker_once(
            redis_client,
            stream_name,
            group_name,
            consumer_name,
            llm_client=llm_client,
        ) is True
        assert await run_worker_once(
            redis_client,
            stream_name,
            group_name,
            consumer_name,
            llm_client=llm_client,
        ) is False
    finally:
        await redis_client.delete(stream_name)
        await redis_client.aclose()
