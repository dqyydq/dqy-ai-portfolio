import uuid

from app.db.redis import create_redis_client
from app.services.llm_cache_service import (
    LLM_CACHE_PREFIX,
    LLM_CACHE_TTL_SECONDS,
    LLM_CACHE_VERSION,
    build_llm_cache_key,
    cache_llm_response,
    get_cached_llm_response,
)


def test_llm_cache_key_is_deterministic_and_hides_prompt_content() -> None:
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Explain async/await in Chinese."},
    ]

    first_key = build_llm_cache_key("deepseek-chat", messages, "conversation:one")
    second_key = build_llm_cache_key("deepseek-chat", messages, "conversation:one")

    assert first_key == second_key
    assert first_key.startswith(f"{LLM_CACHE_PREFIX}:{LLM_CACHE_VERSION}:")
    assert "async/await" not in first_key


def test_llm_cache_key_changes_when_model_or_context_changes() -> None:
    messages = [{"role": "user", "content": "What is Redis?"}]

    original_key = build_llm_cache_key("deepseek-chat", messages, "conversation:one")
    different_model_key = build_llm_cache_key("gpt-4.1-mini", messages, "conversation:one")
    different_context_key = build_llm_cache_key(
        "deepseek-chat",
        [
            {"role": "system", "content": "Answer for senior engineers."},
            {"role": "user", "content": "What is Redis?"},
        ],
        "conversation:one",
    )

    assert different_model_key != original_key
    different_scope_key = build_llm_cache_key(
        "deepseek-chat",
        messages,
        "conversation:two",
    )

    assert different_context_key != original_key
    assert different_scope_key != original_key


async def test_llm_cache_reads_writes_and_expires_responses() -> None:
    redis_client = create_redis_client()
    request_id = uuid.uuid4().hex
    cache_key = build_llm_cache_key(
        "test-model",
        [{"role": "user", "content": f"cache-test-{request_id}"}],
        "conversation:integration",
    )
    other_key = build_llm_cache_key(
        "test-model",
        [{"role": "user", "content": f"cache-test-other-{request_id}"}],
        "conversation:integration",
    )

    try:
        assert await get_cached_llm_response(redis_client, cache_key) is None

        await cache_llm_response(redis_client, cache_key, "cached answer")
        await cache_llm_response(redis_client, other_key, "other cached answer")

        assert await get_cached_llm_response(redis_client, cache_key) == "cached answer"
        assert await get_cached_llm_response(redis_client, other_key) == "other cached answer"

        ttl = await redis_client.ttl(cache_key)
        assert 0 < ttl <= LLM_CACHE_TTL_SECONDS
    finally:
        await redis_client.delete(cache_key, other_key)
        await redis_client.aclose()
