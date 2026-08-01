from uuid import UUID

import json

from app.models.conversation import MessageRole
from redis.asyncio import Redis

MEMORY_PREFIX = "agent:memory:conversation"
MEMORY_WINDOW_SIZE = 12
MEMORY_TTL_SECONDS = 60 * 60 * 24


def build_memory_key(conversation_id: UUID) -> str:
    return f"{MEMORY_PREFIX}:{conversation_id}"


async def append_memory_message(
        redis_client: Redis,
        conversation_id:UUID,
        role:MessageRole,
        content:str
)->None:

    key=build_memory_key(conversation_id)
    message_json=json.dumps(
        {
            "role":role.value,
            "content":content
        },
        ensure_ascii=False
    )
    pipeline=redis_client.pipeline(transaction=True)
    pipeline.rpush(key,message_json)
    pipeline.ltrim(key,-MEMORY_WINDOW_SIZE,-1)
    pipeline.expire(key,MEMORY_TTL_SECONDS)
    await pipeline.execute()


async def get_memory_messages(
        redis_client: Redis,
        conversation_id:UUID
)->list[dict[str,str]]:
    key=build_memory_key(conversation_id)
    raw_messages=await redis_client.lrange(key,0,-1)
    return [
        json.loads(raw_message)
        for raw_message in raw_messages
    ]
