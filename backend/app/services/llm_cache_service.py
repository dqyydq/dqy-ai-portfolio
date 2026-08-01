from hashlib import sha256
import json
from redis.asyncio import Redis

LLM_CACHE_TTL_SECONDS = 60 * 60
LLM_CACHE_PREFIX = "agent:llm:cache"
LLM_CACHE_VERSION = "v1"


def build_llm_cache_key(
    model: str,
    messages: list[dict[str, str]],
    cache_scope:str
) -> str:
    payload = {
        "cache_scope": cache_scope,
        "cache_version": LLM_CACHE_VERSION,
        "model": model,
        "messages": messages,
    }
    canonical_json=json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",",":")
    )
    cache_hash=sha256(canonical_json.encode("utf-8")).hexdigest()

    return f"{LLM_CACHE_PREFIX}:{LLM_CACHE_VERSION}:{cache_hash}"



async def get_cached_llm_response(
    redis_client: Redis,
    cache_key: str,
) -> str | None:
    return await redis_client.get(cache_key)


async def cache_llm_response(
    redis_client: Redis,
    cache_key: str,
    response_text: str,
) -> None:
    await redis_client.set(
        cache_key,
        response_text,
        ex=LLM_CACHE_TTL_SECONDS
    )