import asyncio

from redis.asyncio import Redis
from redis.exceptions import ResponseError
from uuid import UUID
from openai import AsyncOpenAI

from app.clients.llm_client import LLMClient
from app.core.config import get_settings
from app.db.database import session_factory
from app.services.interview_review_worker_service import (
    process_interview_review_task,
)
from app.services.interview_review_queue_service import (
    INTERVIEW_REVIEW_STREAM,
)

INTERVIEW_REVIEW_GROUP = "interview-review-workers"
INTERVIEW_REVIEW_CONSUMER = "worker-1"


async def ensure_consumer_group(
    redis_client: Redis,
    stream_name: str = INTERVIEW_REVIEW_STREAM,
    group_name: str = INTERVIEW_REVIEW_GROUP,
) -> None:
    try:
        await redis_client.xgroup_create(
            stream_name,
            group_name,
            id="0",
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise

async def run_worker_once(
    redis_client: Redis,
    stream_name: str = INTERVIEW_REVIEW_STREAM,
    group_name: str = INTERVIEW_REVIEW_GROUP,
    consumer_name: str = INTERVIEW_REVIEW_CONSUMER,
    *,
    llm_client,
) -> bool:
    messages = await redis_client.xreadgroup(
        groupname=group_name,
        consumername=consumer_name,
        streams={stream_name: ">"},
        count=1,
        block=1000,
    )

    if not messages:
        return False

    stream_name, entries = messages[0]
    message_id, fields = entries[0]

    # 下一步：根据 fields["task_id"] 查询 PostgreSQL，
    # 执行 queued -> running -> completed，
    # 成功后才 XACK。
    task_id = UUID(fields["task_id"])

    async with session_factory() as session:
        await process_interview_review_task(
        session=session,
        task_id=task_id,
        llm_client=llm_client,
        redis_client=redis_client,
    )

    await redis_client.xack(
        stream_name,
        group_name,
        message_id,
    )
    return True
    


async def main() -> None:
    from app.db.redis import create_redis_client

    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    openai_client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=settings.llm_timeout_seconds,
    )
    llm_client = LLMClient(client=openai_client, settings=settings)
    redis_client = create_redis_client()
    try:
        await ensure_consumer_group(redis_client)
        while True:
            await run_worker_once(redis_client, llm_client=llm_client)
    finally:
        await redis_client.aclose()
        await openai_client.close()


if __name__ == "__main__":
    asyncio.run(main())
