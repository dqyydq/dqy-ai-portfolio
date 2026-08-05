import logging
import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interview_review_task import InterviewReviewTask
from app.services.interview_review_queue_service import (
    publish_interview_review_task,
)

logger = logging.getLogger(__name__)


class InterviewReviewDispatchError(Exception):
    def __init__(self, task_id: uuid.UUID) -> None:
        super().__init__("Interview review task dispatch failed")
        self.task_id = task_id


async def create_and_publish_interview_review_task(
    session: AsyncSession,
    redis_client: Redis,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    learning_day: int,
    session_id: uuid.UUID | None = None,
) -> InterviewReviewTask:
    task = InterviewReviewTask(
        user_id=user_id,
        conversation_id=conversation_id,
        session_id=session_id or uuid.uuid4(),
        learning_day=learning_day,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    try:
        await publish_interview_review_task(
            redis_client=redis_client,
            task_id=task.id,
        )
    except RedisError as exc:
        logger.error(
            "Interview review task was persisted but could not be dispatched: %s",
            task.id,
            exc_info=True,
        )
        raise InterviewReviewDispatchError(task.id) from exc

    return task
