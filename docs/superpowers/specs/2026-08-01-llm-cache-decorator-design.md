# LLM cache decorator design

## Goal

Add exact-match Redis response caching without coupling the provider-facing `LLMClient` to Redis or forcing every future LLM use case to share one cache namespace.

## Components

- `LLMClient`: remains responsible only for calling the configured OpenAI-compatible provider and validating its response.
- `llm_cache_service`: builds deterministic keys and reads/writes text responses with a one-hour TTL.
- `CachedLLMClient`: wraps one `LLMClient` and one Redis client. It owns cache-aside orchestration.
- Conversation flow: explicitly calls `CachedLLMClient.generate(messages, cache_scope=f"conversation:{conversation_id}")`.

## Data flow

1. Build a key from cache version, cache scope, model, and ordered messages.
2. Read Redis.
3. On a non-empty cached response, return it and do not call the provider.
4. On a miss, call `LLMClient.generate` once.
5. Cache only the successful non-empty response with a 3600-second TTL, then return it.

## Failure behavior

- Redis read or write errors are logged and treated as a cache miss; the provider call continues.
- Provider failures propagate as the existing LLM errors and are never cached.
- Cache scope is part of both the Redis key prefix/payload. The conversation scope includes `conversation_id`, so even identical requests from separate conversation threads never share a response.

## Tests

- Cache hit returns the stored response and records zero provider calls.
- Cache miss calls the provider exactly once and stores its response.
- Redis failure still calls the provider successfully.
- The existing key tests continue to prove model, context, and scope isolation.

## Scope limits

This is exact-match response caching only. It excludes semantic/vector caching, single-flight request coalescing, streaming, token accounting, and cache invalidation beyond TTL/version changes.
