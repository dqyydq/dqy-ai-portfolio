from redis.exceptions import ConnectionError as RedisConnectionError

from app.clients.cached_llm_client import CachedLLMClient
from app.services.llm_cache_service import build_llm_cache_key


class FakeProviderClient:
    def __init__(self, response: str = "provider answer") -> None:
        self.response = response
        self.calls: list[list[dict[str, str]]] = []

    async def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.response


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.values[key] = value
        self.ttls[key] = ex


class UnavailableRedis:
    async def get(self, *_args, **_kwargs):
        raise RedisConnectionError("Redis is unavailable")

    async def set(self, *_args, **_kwargs):
        raise RedisConnectionError("Redis is unavailable")


async def test_cached_llm_client_returns_hit_without_provider_call() -> None:
    messages = [{"role": "user", "content": "Explain Redis."}]
    scope = "conversation:one"
    redis_client = FakeRedis()
    provider = FakeProviderClient()
    cached_client = CachedLLMClient(provider, redis_client, "test-model")
    cache_key = build_llm_cache_key("test-model", messages, scope)
    redis_client.values[cache_key] = "cached answer"

    response = await cached_client.generate(messages, cache_scope=scope)

    assert response == "cached answer"
    assert provider.calls == []


async def test_cached_llm_client_calls_provider_once_and_caches_miss() -> None:
    messages = [{"role": "user", "content": "Explain Redis."}]
    scope = "conversation:one"
    redis_client = FakeRedis()
    provider = FakeProviderClient("fresh answer")
    cached_client = CachedLLMClient(provider, redis_client, "test-model")

    response = await cached_client.generate(messages, cache_scope=scope)

    cache_key = build_llm_cache_key("test-model", messages, scope)
    assert response == "fresh answer"
    assert provider.calls == [messages]
    assert redis_client.values[cache_key] == "fresh answer"
    assert redis_client.ttls[cache_key] == 3600


async def test_cached_llm_client_falls_back_when_redis_is_unavailable() -> None:
    messages = [{"role": "user", "content": "Explain Redis."}]
    provider = FakeProviderClient("fresh answer")
    cached_client = CachedLLMClient(provider, UnavailableRedis(), "test-model")

    response = await cached_client.generate(
        messages,
        cache_scope="conversation:one",
    )

    assert response == "fresh answer"
    assert provider.calls == [messages]
