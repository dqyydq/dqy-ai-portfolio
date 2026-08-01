# Chat rate-limit design

## Goal

Protect authenticated LLM message-generation requests from accidental loops, abuse, and provider-cost spikes with a per-user Redis fixed-window limit.

## Policy

- Protected endpoint: `POST /conversations/{conversation_id}/messages`.
- Owner: authenticated `user_id`, shared across all of that user's conversations.
- Limit: 10 requests per 60-second window, starting with the first request in the window.
- Redis key: `agent:rate-limit:message:v1:{user_id}`.
- Over limit: HTTP 429 with `Retry-After`, `X-RateLimit-Limit`, and `X-RateLimit-Remaining` headers.
- Redis unavailable: fail closed with HTTP 503; do not call the LLM.

## Atomic algorithm

A Lua script receives the one Redis key and window length:

1. `INCR` the key.
2. If the count is one, set `EXPIRE key 60`.
3. Read `TTL` and return count plus remaining seconds.

Redis executes one Lua script atomically. This prevents a process failure between increment and initial expiry from creating a permanent rate-limit key. The expiry is not refreshed for later requests, so the window remains fixed.

## Integration

- A FastAPI dependency runs after authentication, obtaining `user_id` and the lifecycle-owned Redis client.
- The message route depends on the limiter before calling conversation generation.
- The dependency returns limit metadata for allowed requests or raises the mapped HTTP error.

## Tests and limits

- Test the first request creates a TTL, request 10 is allowed, and request 11 is denied with 429 metadata.
- Test users have isolated keys.
- Test Redis failure maps to 503 and prevents LLM generation.
- The design does not implement IP limits, sliding windows, distributed multi-key quotas, or queue workers.
