from uuid import uuid4

from app.db.redis import create_redis_client
from app.services.rate_limit_service import (
    RATE_LIMIT_MAX_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    build_rate_limit_key,
    check_message_rate_limit,
)


async def test_message_rate_limit_allows_window_then_denies_and_sets_ttl() -> None:
    redis_client = create_redis_client()
    user_id = uuid4()
    key = build_rate_limit_key(user_id)

    try:
        first_result = await check_message_rate_limit(redis_client, user_id)

        assert first_result.allowed is True
        assert first_result.limit == RATE_LIMIT_MAX_REQUESTS
        assert first_result.remaining == RATE_LIMIT_MAX_REQUESTS - 1
        assert 0 < first_result.retry_after <= RATE_LIMIT_WINDOW_SECONDS

        for _ in range(RATE_LIMIT_MAX_REQUESTS - 1):
            last_allowed_result = await check_message_rate_limit(redis_client, user_id)

        denied_result = await check_message_rate_limit(redis_client, user_id)

        assert last_allowed_result.allowed is True
        assert last_allowed_result.remaining == 0
        assert denied_result.allowed is False
        assert denied_result.remaining == 0
        assert 0 < denied_result.retry_after <= RATE_LIMIT_WINDOW_SECONDS
    finally:
        await redis_client.delete(key)
        await redis_client.aclose()


async def test_message_rate_limit_is_isolated_per_user() -> None:
    redis_client = create_redis_client()
    first_user_id = uuid4()
    second_user_id = uuid4()
    first_key = build_rate_limit_key(first_user_id)
    second_key = build_rate_limit_key(second_user_id)

    try:
        for _ in range(RATE_LIMIT_MAX_REQUESTS):
            await check_message_rate_limit(redis_client, first_user_id)

        first_user_denied = await check_message_rate_limit(redis_client, first_user_id)
        second_user_first_request = await check_message_rate_limit(redis_client, second_user_id)

        assert first_user_denied.allowed is False
        assert second_user_first_request.allowed is True
        assert second_user_first_request.remaining == RATE_LIMIT_MAX_REQUESTS - 1
    finally:
        await redis_client.delete(first_key, second_key)
        await redis_client.aclose()
