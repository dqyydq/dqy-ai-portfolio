import uuid

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import delete

from app.clients.llm_client import LLMCallError
from app.api.auth_schemas import RegisterRequest
from app.api.conversation_schemas import ConversationCreate, MessageCreate
from app.db.database import close_database, init_db, session_factory
from app.models.conversation import Conversation, Message, MessageRole
from app.models.user import User
from app.services.auth_service import create_user
from app.services.conversation_service import (
    ConversationNotFoundError,
    build_llm_history,
    create_conversation,
    create_user_message,
    get_conversation_for_user,
    list_messages,
    send_message_and_generate,
)


class FakeLLMClient:
    def __init__(self, answer: str = "Mock assistant reply") -> None:
        self.answer = answer
        self.histories = []

    async def generate(self, history, cache_scope: str | None = None):
        self.histories.append(history)
        return self.answer


class FailingLLMClient:
    async def generate(self, history, cache_scope: str | None = None):
        raise LLMCallError("LLM request failed")


class UnavailableRedis:
    async def lrange(self, *_args, **_kwargs):
        raise RedisConnectionError("Redis is unavailable")

    def pipeline(self, *_args, **_kwargs):
        raise RedisConnectionError("Redis is unavailable")


def test_build_llm_history_preserves_order_for_chat_completions() -> None:
    conversation_id = uuid.uuid4()
    messages = [
        Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content="First question",
        ),
        Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content="First answer",
        ),
    ]

    history = build_llm_history(messages)

    assert history == [
        {
            "role": "user",
            "content": "First question",
        },
        {
            "role": "assistant",
            "content": "First answer",
        },
    ]


async def test_create_conversation_persists_owner_and_title() -> None:
    email = f"conversation-{uuid.uuid4()}@example.com"

    await init_db()
    user_id = None

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

        async with session_factory() as session:
            conversation = await create_conversation(
                session,
                user_id=user_id,
                data=ConversationCreate(title="Day 3 learning"),
            )

        async with session_factory() as session:
            persisted = await session.get(Conversation, conversation.id)

        assert persisted is not None
        assert persisted.user_id == user_id
        assert persisted.title == "Day 3 learning"
        assert persisted.created_at is not None
    finally:
        async with session_factory() as session:
            if user_id is not None:
                await session.execute(
                    delete(Conversation).where(Conversation.user_id == user_id),
                )
                await session.execute(delete(User).where(User.id == user_id))
                await session.commit()
        await close_database()


async def test_get_conversation_for_user_hides_other_users_conversation() -> None:
    first_email = f"owner-{uuid.uuid4()}@example.com"
    second_email = f"other-{uuid.uuid4()}@example.com"
    user_ids = []

    await init_db()

    try:
        async with session_factory() as session:
            first_user = await create_user(
                session,
                RegisterRequest(
                    email=first_email,
                    user_name=f"owner_{uuid.uuid4().hex[:12]}",
                    password="correct horse battery staple",
                ),
            )
            second_user = await create_user(
                session,
                RegisterRequest(
                    email=second_email,
                    user_name=f"other_{uuid.uuid4().hex[:12]}",
                    password="correct horse battery staple",
                ),
            )
            user_ids = [first_user.id, second_user.id]

        async with session_factory() as session:
            conversation = await create_conversation(
                session,
                user_id=first_user.id,
                data=ConversationCreate(title="Private conversation"),
            )

        async with session_factory() as session:
            owner_result = await get_conversation_for_user(
                session,
                conversation_id=conversation.id,
                user_id=first_user.id,
            )
            other_user_result = await get_conversation_for_user(
                session,
                conversation_id=conversation.id,
                user_id=second_user.id,
            )

        assert owner_result is not None
        assert owner_result.id == conversation.id
        assert other_user_result is None
    finally:
        async with session_factory() as session:
            if user_ids:
                await session.execute(
                    delete(Conversation).where(Conversation.user_id.in_(user_ids)),
                )
                await session.execute(delete(User).where(User.id.in_(user_ids)))
                await session.commit()
        await close_database()


async def test_create_user_message_persists_user_role() -> None:
    email = f"message-{uuid.uuid4()}@example.com"
    user_id = None
    conversation_id = None

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

        async with session_factory() as session:
            conversation = await create_conversation(
                session,
                user_id=user_id,
                data=ConversationCreate(title="Message test"),
            )
            conversation_id = conversation.id

        async with session_factory() as session:
            message = await create_user_message(
                session,
                conversation_id=conversation_id,
                data=MessageCreate(content="Hello, agent"),
            )

        async with session_factory() as session:
            persisted = await session.get(Message, message.id)

        assert persisted is not None
        assert persisted.conversation_id == conversation_id
        assert persisted.role is MessageRole.USER
        assert persisted.content == "Hello, agent"
    finally:
        async with session_factory() as session:
            if conversation_id is not None:
                await session.execute(
                    delete(Message).where(Message.conversation_id == conversation_id),
                )
                await session.execute(
                    delete(Conversation).where(Conversation.id == conversation_id),
                )
            if user_id is not None:
                await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await close_database()


async def test_send_message_and_generate_persists_user_and_assistant() -> None:
    email = f"generate-{uuid.uuid4()}@example.com"
    user_id = None
    conversation_id = None
    llm_client = FakeLLMClient(answer="Generated answer")

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
                user_id=user_id,
                data=ConversationCreate(title="Generated conversation"),
            )
            conversation_id = conversation.id

            assistant = await send_message_and_generate(
                session=session,
                user_id=user_id,
                conversation_id=conversation_id,
                data=MessageCreate(content="Tell me a fact"),
                llm_client=llm_client,
            )

        assert assistant.role is MessageRole.ASSISTANT
        assert assistant.content == "Generated answer"
        assert llm_client.histories == [
            [
                {
                    "role": "user",
                    "content": "Tell me a fact",
                }
            ]
        ]

        async with session_factory() as session:
            messages = await list_messages(session, conversation_id)

        assert [(message.role, message.content) for message in messages] == [
            (MessageRole.USER, "Tell me a fact"),
            (MessageRole.ASSISTANT, "Generated answer"),
        ]
    finally:
        async with session_factory() as session:
            if conversation_id is not None:
                await session.execute(
                    delete(Message).where(Message.conversation_id == conversation_id),
                )
                await session.execute(
                    delete(Conversation).where(Conversation.id == conversation_id),
                )
            if user_id is not None:
                await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await close_database()


async def test_send_message_and_generate_falls_back_to_postgres_when_redis_fails() -> None:
    email = f"redis-fallback-{uuid.uuid4()}@example.com"
    user_id = None
    conversation_id = None
    llm_client = FakeLLMClient()

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
                user_id=user_id,
                data=ConversationCreate(title="Redis fallback conversation"),
            )
            conversation_id = conversation.id

            assistant = await send_message_and_generate(
                session=session,
                user_id=user_id,
                conversation_id=conversation_id,
                data=MessageCreate(content="Redis can fail safely"),
                llm_client=llm_client,
                redis_client=UnavailableRedis(),
            )

        assert assistant.content == "Mock assistant reply"
        assert llm_client.histories == [
            [{"role": "user", "content": "Redis can fail safely"}],
        ]

        async with session_factory() as session:
            messages = await list_messages(session, conversation_id)

        assert [message.role for message in messages] == [
            MessageRole.USER,
            MessageRole.ASSISTANT,
        ]
    finally:
        async with session_factory() as session:
            if conversation_id is not None:
                await session.execute(
                    delete(Message).where(Message.conversation_id == conversation_id),
                )
                await session.execute(
                    delete(Conversation).where(Conversation.id == conversation_id),
                )
            if user_id is not None:
                await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await close_database()


async def test_send_message_and_generate_keeps_user_message_when_llm_fails() -> None:
    email = f"failed-generate-{uuid.uuid4()}@example.com"
    user_id = None
    conversation_id = None

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
                user_id=user_id,
                data=ConversationCreate(title="Failure conversation"),
            )
            conversation_id = conversation.id

            with pytest.raises(LLMCallError, match="LLM request failed"):
                await send_message_and_generate(
                    session=session,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    data=MessageCreate(content="Do not lose this"),
                    llm_client=FailingLLMClient(),
                )

        async with session_factory() as session:
            messages = await list_messages(session, conversation_id)

        assert [(message.role, message.content) for message in messages] == [
            (MessageRole.USER, "Do not lose this"),
        ]
    finally:
        async with session_factory() as session:
            if conversation_id is not None:
                await session.execute(
                    delete(Message).where(Message.conversation_id == conversation_id),
                )
                await session.execute(
                    delete(Conversation).where(Conversation.id == conversation_id),
                )
            if user_id is not None:
                await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await close_database()


async def test_send_message_and_generate_rejects_other_user_before_llm_call() -> None:
    first_email = f"owner-generate-{uuid.uuid4()}@example.com"
    second_email = f"other-generate-{uuid.uuid4()}@example.com"
    user_ids = []
    conversation_id = None
    llm_client = FakeLLMClient()

    await init_db()
    try:
        async with session_factory() as session:
            owner = await create_user(
                session,
                RegisterRequest(
                    email=first_email,
                    user_name=f"owner_{uuid.uuid4().hex[:12]}",
                    password="correct horse battery staple",
                ),
            )
            other_user = await create_user(
                session,
                RegisterRequest(
                    email=second_email,
                    user_name=f"other_{uuid.uuid4().hex[:12]}",
                    password="correct horse battery staple",
                ),
            )
            user_ids = [owner.id, other_user.id]
            conversation = await create_conversation(
                session,
                user_id=owner.id,
                data=ConversationCreate(title="Private generated conversation"),
            )
            conversation_id = conversation.id

            with pytest.raises(ConversationNotFoundError):
                await send_message_and_generate(
                    session=session,
                    user_id=other_user.id,
                    conversation_id=conversation_id,
                    data=MessageCreate(content="Not allowed"),
                    llm_client=llm_client,
                )

        assert llm_client.histories == []
        async with session_factory() as session:
            messages = await list_messages(session, conversation_id)
        assert messages == []
    finally:
        async with session_factory() as session:
            if conversation_id is not None:
                await session.execute(
                    delete(Message).where(Message.conversation_id == conversation_id),
                )
                await session.execute(
                    delete(Conversation).where(Conversation.id == conversation_id),
                )
            if user_ids:
                await session.execute(delete(User).where(User.id.in_(user_ids)))
            await session.commit()
        await close_database()
