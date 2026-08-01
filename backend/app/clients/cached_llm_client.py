import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.services.llm_cache_service import (
    build_llm_cache_key,
    cache_llm_response,
    get_cached_llm_response,
)

logger = logging.getLogger(__name__)


class CachedLLMClient:
    def __init__(
        self,
        llm_client,
        redis_client: Redis,
        model: str,
    ) -> None:
        self._llm_client = llm_client
        self._redis_client = redis_client
        self._model = model

    async def generate(
        self,
        messages: list[dict[str, str]],
        cache_scope: str,
    ) -> str:
        cache_key = build_llm_cache_key(
            model=self._model,
            messages=messages,
            cache_scope=cache_scope,
        )

        try:
            cached_response = await get_cached_llm_response(
                self._redis_client,
                cache_key,
            )
            if cached_response is not None:
                return cached_response
        except RedisError:
            logger.warning(
                "LLM cache read failed; calling the provider directly",
                exc_info=True,
            )

        response_text = await self._llm_client.generate(messages)

        try:
            await cache_llm_response(
                self._redis_client,
                cache_key,
                response_text,
            )
        except RedisError:
            logger.warning(
                "LLM cache write failed; returning provider response",
                exc_info=True,
            )

        return response_text