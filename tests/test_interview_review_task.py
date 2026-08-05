import uuid

from sqlalchemy import delete

from app.api.auth_schemas import RegisterRequest
from app.api.conversation_schemas import ConversationCreate
from app.db.database import close_database, init_db, session_factory
from app.models.conversation import Conversation
from app.models.interview_review_task import (
    InterviewReviewStatus,
    InterviewReviewTask,
)
from app.models.user import User
from app.services.auth_service import create_user
from app.services.conversation_service import create_conversation


async def test_interview_review_task_persists_queued_state_and_references() -> None:
    email = f"review-task-{uuid.uuid4()}@example.com"
    user_id = None
    conversation_id = None
    task_id = None
    session_id = uuid.uuid4()

    await init_db()
    try:
        async with session_factory() as session:
            user = await create_user(
                session,
                RegisterRequest(
                    email=email,
                    user_name=f"user_{uuid.uuid4().hex[:12]}",
                    password="correct horse battery staple",
                ),
            )
            user_id = user.id
            conversation = await create_conversation(
                session,
                user_id=user.id,
                data=ConversationCreate(title="Interview practice"),
            )
            conversation_id = conversation.id

            task = InterviewReviewTask(
                user_id=user.id,
                conversation_id=conversation.id,
                session_id=session_id,
                learning_day=6,
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            task_id = task.id

        async with session_factory() as session:
            persisted = await session.get(InterviewReviewTask, task_id)

        assert persisted is not None
        assert persisted.user_id == user_id
        assert persisted.conversation_id == conversation_id
        assert persisted.session_id == session_id
        assert persisted.learning_day == 6
        assert persisted.status is InterviewReviewStatus.QUEUED
        assert persisted.result is None
        assert persisted.error_message is None
        assert persisted.created_at is not None
        assert persisted.started_at is None
        assert persisted.completed_at is None
    finally:
        async with session_factory() as session:
            if task_id is not None:
                await session.execute(
                    delete(InterviewReviewTask).where(
                        InterviewReviewTask.id == task_id,
                    ),
                )
            if conversation_id is not None:
                await session.execute(
                    delete(Conversation).where(Conversation.id == conversation_id),
                )
            if user_id is not None:
                await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await close_database()
