from datetime import datetime, timezone
from uuid import UUID
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import publish_user_realtime_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Message
from app.models.interview_review_task import (
    InterviewReviewStatus,
    InterviewReviewTask,
)
from app.services.learning_material_service import load_learning_day_material

logger = logging.getLogger(__name__)

def build_interview_review_prompt(
    learning_day: int,
    learning_material: str,
    messages: list[Message],
) -> list[dict[str, str]]:
    transcript = "\n\n".join(
        f"[{message.role.value}] {message.content}" for message in messages
    )
    return [
        {
            "role": "system",
            "content": (
                "You are a rigorous backend interview coach. Review only the "
                "learner evidence in the transcript. Return Markdown with these "
                "headings: ## Summary, ## What You Understand, ## Corrections, "
                "## Model Answers, ## Follow-up Questions, ## Next Practice. "
                "Do not invent answers the learner did not give."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Project learning material for Day {learning_day}:\n\n"
                f"{learning_material}\n\n"
                f"Conversation transcript:\n\n{transcript}"
            ),
        },
    ]


async def publish_review_event(
    redis_client: Redis,
    task: InterviewReviewTask,
    event_type: RealtimeEventType,
) -> None:
    try:
        await publish_user_realtime_event(
            redis_client=redis_client,
            user_id=task.user_id,
            event=RealtimeEvent(
                type=event_type,
                conversation_id=task.conversation_id,
                task_id=task.id,
                data={"status": task.status.value},
            ),
        )
    except RedisError:
        logger.warning(
            "Realtime review event publish failed for task %s",
            task.id,
            exc_info=True,
        )


async def process_interview_review_task(
    session: AsyncSession,
    task_id: UUID,
    llm_client,
    redis_client: Redis,
) -> bool:
    task = await session.get(InterviewReviewTask, task_id)

    if task is None:
        return False
    if task.status in {InterviewReviewStatus.COMPLETED, InterviewReviewStatus.FAILED}:
        return False

    if task.status is InterviewReviewStatus.QUEUED:
        task.status = InterviewReviewStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        await session.commit()
        await publish_review_event(
        redis_client=redis_client,
        task=task,
        event_type=RealtimeEventType.REVIEW_STATUS,
    )

    try:
        messages = list(
            (
                await session.scalars(
                    select(Message)
                    .where(Message.conversation_id == task.conversation_id)
                    .order_by(Message.created_at.asc()),
                )
            ).all(),
        )
        prompt = build_interview_review_prompt(
            learning_day=task.learning_day,
            learning_material=load_learning_day_material(task.learning_day),
            messages=messages,
        )
        task.result = await llm_client.generate(prompt)
        task.status = InterviewReviewStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await publish_review_event(
        redis_client=redis_client,
        task=task,
        event_type=RealtimeEventType.REVIEW_COMPLETED,
    )
            
        return True
    except Exception as exc:
        task.status = InterviewReviewStatus.FAILED
        task.error_message = "Interview review generation failed"
        task.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await publish_review_event(
        redis_client=redis_client,
        task=task,
        event_type=RealtimeEventType.REVIEW_FAILED,
    )
        raise
