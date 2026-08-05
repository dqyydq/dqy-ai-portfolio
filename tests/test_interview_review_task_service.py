import asyncio
import json
import uuid

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import delete, select

from app.api.auth_schemas import RegisterRequest
from app.api.conversation_schemas import ConversationCreate
from app.db.database import close_database, init_db, session_factory
from app.db.redis import create_redis_client
from app.models.conversation import Conversation
from app.models.interview_review_task import (
    InterviewReviewStatus,
    InterviewReviewTask,
)
from app.models.user import User
from app.services.auth_service import create_user
from app.services.conversation_service import create_conversation
from app.services.interview_review_queue_service import INTERVIEW_REVIEW_STREAM
from app.services.interview_review_task_service import (
    InterviewReviewDispatchError,
    create_and_publish_interview_review_task,
)
from app.realtime.publisher import build_user_realtime_channel
from app.workers.interview_review_worker import (
    ensure_consumer_group,
    run_worker_once,
)


class FakeLLMClient:
    def __init__(self, answer: str = "## Summary\nStrong Redis Streams answer.") -> None:
        self.answer = answer
        self.prompts = []

    async def generate(self, prompt):
        self.prompts.append(prompt)
        return self.answer


class UnavailableRedis:
    async def xadd(self, *_args, **_kwargs):
        raise RedisConnectionError("Redis is unavailable")


async def _read_realtime_events(pubsub, count: int) -> list[dict]:
    events = []
    for _ in range(30):
        message = await pubsub.get_message(
            ignore_subscribe_messages=True,
            timeout=0.1,
        )
        if message is not None:
            events.append(json.loads(message["data"]))
            if len(events) == count:
                return events
        await asyncio.sleep(0.01)
    return events


async def _create_task_context():
    email = f"queue-task-{uuid.uuid4()}@example.com"
    async with session_factory() as session:
        user = await create_user(session, RegisterRequest(
            email=email, user_name=f"user_{uuid.uuid4().hex[:12]}",
            password="correct horse battery staple",
        ))
        conversation = await create_conversation(
            session,
            user.id,
            ConversationCreate(
                title="Interview queue",
                mode="project_interview",
                learning_day=6,
            ),
        )
    return email, user.id, conversation.id


async def _cleanup_task_context(email: str, task_id=None) -> None:
    async with session_factory() as session:
        if task_id is not None:
            await session.execute(delete(InterviewReviewTask).where(InterviewReviewTask.id == task_id))
        user = await session.scalar(select(User).where(User.email == email))
        if user is not None:
            await session.execute(delete(Conversation).where(Conversation.user_id == user.id))
            await session.execute(delete(User).where(User.id == user.id))
        await session.commit()
    await close_database()


async def test_create_and_publish_task_persists_then_dispatches() -> None:
    await init_db()
    email, user_id, conversation_id = await _create_task_context()
    redis_client = create_redis_client()
    task_id = None
    message_id = None
    try:
        async with session_factory() as session:
            task = await create_and_publish_interview_review_task(
                session, redis_client, user_id, conversation_id, 6,
            )
            task_id = task.id
        entries = await redis_client.xrevrange(INTERVIEW_REVIEW_STREAM, count=1)
        message_id, fields = entries[0]
        assert fields["task_id"] == str(task_id)
        assert task.status is InterviewReviewStatus.QUEUED
    finally:
        if message_id is not None:
            await redis_client.xdel(INTERVIEW_REVIEW_STREAM, message_id)
        await redis_client.aclose()
        await _cleanup_task_context(email, task_id)


async def test_dispatch_failure_keeps_queued_task_in_postgres() -> None:
    await init_db()
    email, user_id, conversation_id = await _create_task_context()
    task_id = None
    try:
        async with session_factory() as session:
            with pytest.raises(InterviewReviewDispatchError) as error:
                await create_and_publish_interview_review_task(
                    session, UnavailableRedis(), user_id, conversation_id, 6,
                )
            task_id = error.value.task_id
        async with session_factory() as session:
            task = await session.get(InterviewReviewTask, task_id)
        assert task is not None
        assert task.status is InterviewReviewStatus.QUEUED
    finally:
        await _cleanup_task_context(email, task_id)


async def test_worker_completes_task_then_acknowledges_stream_message() -> None:
    await init_db()
    email, user_id, conversation_id = await _create_task_context()
    redis_client = create_redis_client()
    task_id = None
    stream_name = f"agent:test:review-worker:{uuid.uuid4().hex}"
    group_name = f"group-{uuid.uuid4().hex}"
    consumer_name = f"consumer-{uuid.uuid4().hex}"
    llm_client = FakeLLMClient()
    subscriber = create_redis_client()
    pubsub = subscriber.pubsub()

    try:
        async with session_factory() as session:
            task = InterviewReviewTask(
                user_id=user_id,
                conversation_id=conversation_id,
                session_id=uuid.uuid4(),
                learning_day=6,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            task_id = task.id

        await pubsub.subscribe(build_user_realtime_channel(user_id))
        await ensure_consumer_group(redis_client, stream_name, group_name)
        await redis_client.xadd(stream_name, {"task_id": str(task_id)})

        assert await run_worker_once(
            redis_client,
            stream_name,
            group_name,
            consumer_name,
            llm_client=llm_client,
        ) is True

        async with session_factory() as session:
            persisted = await session.get(InterviewReviewTask, task_id)

        pending = await redis_client.xpending(stream_name, group_name)
        events = await _read_realtime_events(pubsub, count=2)
        assert persisted.status is InterviewReviewStatus.COMPLETED
        assert persisted.result == "## Summary\nStrong Redis Streams answer."
        assert persisted.started_at is not None
        assert persisted.completed_at is not None
        assert pending["pending"] == 0
        assert "Day 6" in llm_client.prompts[0][1]["content"]
        assert [event["type"] for event in events] == [
            "review.status",
            "review.completed",
        ]
        assert events[0]["data"] == {"status": "running"}
        assert events[1]["data"] == {"status": "completed"}
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()
        await subscriber.aclose()
        await redis_client.delete(stream_name)
        await redis_client.aclose()
        await _cleanup_task_context(email, task_id)
