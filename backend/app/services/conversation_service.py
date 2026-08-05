from app.models.conversation import Conversation,Message
from app.core.security import get_password_hash,verify_password
from app.api.conversation_schemas import ConversationCreate, ConversationLearningContextUpdate, ConversationResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from sqlalchemy import select
from app.api.conversation_schemas import MessageCreate
from app.models.conversation import ConversationMode, MessageRole
import logging
logger = logging.getLogger(__name__)
from redis.exceptions import RedisError
from redis.asyncio import Redis
from collections.abc import AsyncIterator
from app.clients.llm_client import LLMCallError
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.services.memory_service import (
    MEMORY_WINDOW_SIZE,
    append_memory_message,
    get_memory_messages,
)


class ConversationNotFoundError(Exception):
    pass

async def create_conversation(
    session: AsyncSession,
    user_id: UUID,
    data: ConversationCreate,
) -> Conversation:
    conversation=Conversation(
        user_id=user_id,
        title=data.title,
        mode=data.mode,
        learning_day=data.learning_day,
    )

    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations(
    session: AsyncSession,
    user_id: UUID,
) -> list[Conversation]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc()),
    )
    return list(result.scalars().all())



async def get_conversation_for_user(
    session: AsyncSession,
    conversation_id: UUID,
    user_id: UUID,
) -> Conversation | None:
    result=await session.execute(
        select(Conversation).where(
    Conversation.id == conversation_id,
    Conversation.user_id == user_id,
    )
)
    return result.scalar_one_or_none()


async def update_project_interview_learning_day(
    session: AsyncSession,
    conversation: Conversation,
    data: ConversationLearningContextUpdate,
) -> Conversation:
    if conversation.mode is not ConversationMode.PROJECT_INTERVIEW:
        raise ValueError("Conversation is not a project interview")

    conversation.learning_day = data.learning_day
    await session.commit()
    await session.refresh(conversation)
    return conversation



async def create_user_message(
    session: AsyncSession,
    conversation_id: UUID,
    data: MessageCreate,
) -> Message:
    message=Message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=data.content
    )

    session.add(message)
    await session.commit()
    await session.refresh(message)

    return message



async def create_assistant_message(
    session: AsyncSession,
    conversation_id: UUID,
    content: str,
) -> Message:
    message=Message(
    conversation_id=conversation_id,
    role=MessageRole.ASSISTANT,
    content=content
)

    session.add(message)
    await session.commit()
    await session.refresh(message)

    return message


async def list_messages(
    session: AsyncSession,
    conversation_id: UUID,
) -> list[Message]:
    result=await session.execute(
        select(Message)
        .where(Message.conversation_id==conversation_id)
        .order_by(Message.created_at.asc()),
    )
    return list(result.scalars().all())




def build_llm_history(messages: list[Message]) -> list[dict]:
    return [
        {"role": message.role.value, "content": message.content}
        for message in messages
    ]


def build_project_interview_instruction(learning_day: int) -> dict[str, str]:
    return {
        "role": "system",
        "content": (
            "You are the interview coach for the AI Agent Platform learning project. "
            f"This is a dedicated Day {learning_day} project-interview conversation. "
            "Stay within the selected Day's FastAPI, PostgreSQL, Redis, LLM, or Worker "
            "scope. Ask one concrete interview question at a time, wait for the learner's "
            "answer, then assess it with the mechanism, production consequence, and one "
            "follow-up question. Do not act as a generic study-planning assistant."
        ),
    }

async def send_message_and_generate(
    session: AsyncSession,
    user_id: UUID,
    conversation_id: UUID,
    data: MessageCreate,
    llm_client,
    redis_client: Redis | None = None,
) -> Message:
    conversation = await get_conversation_for_user(
        session,
        conversation_id,
        user_id,
    )
    if conversation is None:
        raise ConversationNotFoundError("Conversation not found")

    user_message = await create_user_message(
        session=session,
        conversation_id=conversation_id,
        data=data,
    )

    if redis_client is None:
        history = build_llm_history(
            await list_recent_messages(session, conversation_id, MEMORY_WINDOW_SIZE),
        )
    else:
        history = await get_llm_history_with_memory(
            session=session,
            redis_client=redis_client,
            conversation_id=conversation_id,
            current_message=user_message,
        )

    if (
        conversation.mode is ConversationMode.PROJECT_INTERVIEW
        and conversation.learning_day is not None
    ):
        history = [
            build_project_interview_instruction(conversation.learning_day),
            *history,
        ]

    assistant_content = await llm_client.generate(
    history,
    cache_scope=f"conversation:{conversation_id}",
    )

    assistant_message = await create_assistant_message(
        session=session,
        conversation_id=conversation_id,
        content=assistant_content,
    )

    if redis_client is not None:
        try:
            await append_memory_message(
                redis_client=redis_client,
                conversation_id=conversation_id,
                role=assistant_message.role,
                content=assistant_message.content,
            )
        except RedisError:
            logger.warning(
                "Redis memory write failed after assistant response",
                exc_info=True,
            )

    return assistant_message

async def list_recent_messages(
        session:AsyncSession,
        conversation_id:UUID,
        limit:int
)->list[Message]:
    result= await session.execute(
        select(Message)
        .where(Message.conversation_id==conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages=list(result.scalars().all())
    messages.reverse()
    return messages


async def get_llm_history_with_memory(
        session:AsyncSession,
        redis_client: Redis,
        conversation_id:UUID,
        current_message:Message
)->list[dict[str,str]]:
    try:
        cache_history=await get_memory_messages(redis_client, conversation_id)

        if cache_history:
            await append_memory_message(
                redis_client=redis_client,
                conversation_id=conversation_id,
                role=current_message.role,
                content=current_message.content,
            )

            current_item={
                "role":current_message.role.value,
                "content":current_message.content
            }
            return [
                *cache_history,
                current_item,
            ][-MEMORY_WINDOW_SIZE:]

        recent_messages = await list_recent_messages(
            session=session,
            conversation_id=conversation_id,
            limit=MEMORY_WINDOW_SIZE,
        )

        for message in recent_messages:
            await append_memory_message(
                redis_client=redis_client,
                conversation_id=conversation_id,
                role=message.role,
                content=message.content,
            )

        return build_llm_history(recent_messages)
    except RedisError:
        logger.warning(
            "Redis memory is unavailable; falling back to PostgreSQL",
            exc_info=True,
        )

        recent_messages = await list_recent_messages(
            session=session,
            conversation_id=conversation_id,
            limit=MEMORY_WINDOW_SIZE,
        )

        return build_llm_history(recent_messages)



async def stream_message_generation(
    session: AsyncSession,
    user_id: UUID,
    conversation_id: UUID,
    data: MessageCreate,
    llm_client,
    redis_client: Redis,
) -> AsyncIterator[RealtimeEvent]:
    conversation = await get_conversation_for_user(
        session=session,
        conversation_id=conversation_id,
        user_id=user_id,
    )
    if conversation is None:
        raise ConversationNotFoundError("Conversation not found")

    user_message = await create_user_message(
        session=session,
        conversation_id=conversation_id,
        data=data,
    )

    yield RealtimeEvent(
        type=RealtimeEventType.MESSAGE_STARTED,
        conversation_id=conversation.id,
        data={"user_message_id": str(user_message.id)},
    )

    history = await get_llm_history_with_memory(
        session=session,
        redis_client=redis_client,
        conversation_id=conversation_id,
        current_message=user_message,
    )

    if (
        conversation.mode is ConversationMode.PROJECT_INTERVIEW
        and conversation.learning_day is not None
    ):
        history = [
            build_project_interview_instruction(
                conversation.learning_day,
            ),
            *history,
        ]
    chunks: list[str] = []

    try:
        async for delta in llm_client.stream_generate(
            history,
            cache_scope=f"conversation:{conversation_id}",
        ):
            chunks.append(delta)

            yield RealtimeEvent(
                type=RealtimeEventType.MESSAGE_DELTA,
                conversation_id=conversation.id,
                data={"delta": delta},
            )
    except LLMCallError:
        yield RealtimeEvent(
            type=RealtimeEventType.MESSAGE_FAILED,
            conversation_id=conversation.id,
            data={"detail": "LLM stream request failed"},
        )
        return

    assistant_content = "".join(chunks).strip()

    if not assistant_content:
        yield RealtimeEvent(
            type=RealtimeEventType.MESSAGE_FAILED,
            conversation_id=conversation.id,
            data={"detail": "LLM returned empty stream"},
        )
        return
    assistant_message = await create_assistant_message(
    session=session,
    conversation_id=conversation_id,
    content=assistant_content,)

    try:
        await append_memory_message(
            redis_client=redis_client,
            conversation_id=conversation_id,
            role=assistant_message.role,
            content=assistant_message.content,
        )
    except RedisError:
        logger.warning(
            "Redis memory write failed after streamed assistant response",
            exc_info=True,
        )

    yield RealtimeEvent(
        type=RealtimeEventType.MESSAGE_COMPLETED,
        conversation_id=conversation.id,
        data={
            "message_id": str(assistant_message.id),
        },
    )