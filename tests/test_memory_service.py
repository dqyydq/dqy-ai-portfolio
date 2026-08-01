import uuid

import pytest

from app.db.redis import create_redis_client
from app.models.conversation import MessageRole
from app.services.memory_service import (
    MEMORY_TTL_SECONDS,
    MEMORY_WINDOW_SIZE,
    append_memory_message,
    build_memory_key,
    get_memory_messages,
)


@pytest.mark.asyncio
async def test_memory_keeps_only_the_latest_messages_and_sets_ttl() -> None:
    conversation_id = uuid.uuid4()
    key = build_memory_key(conversation_id)
    redis_client = create_redis_client()

    try:
        for number in range(MEMORY_WINDOW_SIZE + 1):
            await append_memory_message(
                redis_client=redis_client,
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=f"message-{number + 1}",
            )

        messages = await get_memory_messages(redis_client, conversation_id)
        ttl = await redis_client.ttl(key)

        assert len(messages) == MEMORY_WINDOW_SIZE
        assert messages[0] == {"role": "user", "content": "message-2"}
        assert messages[-1] == {"role": "user", "content": "message-13"}
        assert 0 < ttl <= MEMORY_TTL_SECONDS
    finally:
        await redis_client.delete(key)
        await redis_client.aclose()
