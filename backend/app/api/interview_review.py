from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis_client
from app.api.interview_review_schemas import (
    InterviewReviewCreate,
    InterviewReviewResponse,
)
from app.db.database import get_session
from app.models.conversation import ConversationMode
from app.models.interview_review_task import InterviewReviewTask
from app.models.user import User
from app.services.conversation_service import get_conversation_for_user
from app.services.interview_review_task_service import (
    InterviewReviewDispatchError,
    create_and_publish_interview_review_task,
)

router = APIRouter(prefix="/interview-reviews", tags=["interview-reviews"])


@router.post(
    "/conversations/{conversation_id}",
    response_model=InterviewReviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_interview_review(
    conversation_id: UUID,
    data: InterviewReviewCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> InterviewReviewTask:
    conversation = await get_conversation_for_user(
        session=session,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    if (
        conversation.mode is not ConversationMode.PROJECT_INTERVIEW
        or conversation.learning_day is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation is not configured for project interview review",
        )

    try:
        return await create_and_publish_interview_review_task(
            session=session,
            redis_client=redis_client,
            user_id=current_user.id,
            conversation_id=conversation.id,
            learning_day=conversation.learning_day,
        )
    except InterviewReviewDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Interview review was saved but dispatch is pending",
                "task_id": str(exc.task_id),
            },
        ) from exc


@router.get(
    "/{task_id}",
    response_model=InterviewReviewResponse,
)
async def get_interview_review(
    task_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InterviewReviewTask:
    task = await session.scalar(
        select(InterviewReviewTask).where(
            InterviewReviewTask.id == task_id,
            InterviewReviewTask.user_id == current_user.id,
        ),
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview review not found",
        )
    return task
