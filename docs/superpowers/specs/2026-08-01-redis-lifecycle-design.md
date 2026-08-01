# Redis lifecycle ownership design

## Goal

Make the FastAPI application, rather than service modules, own the Redis client lifecycle: create one client during application startup, reuse its connection pool for requests, and close it at shutdown.

## Architecture

- `app.main.lifespan` creates `Redis.from_url(...)` and stores it in `app.state.redis_client`.
- A FastAPI dependency `get_redis_client(request)` returns `request.app.state.redis_client`.
- The conversation route receives that dependency and passes the client into the memory-enabled service path.
- The memory service accepts a `Redis` argument. It does not import an application-global client.
- Readiness receives the same client through dependency injection and calls `PING`.
- Shutdown closes `app.state.redis_client` after normal request handling has finished.

## Data flow

`request -> dependency -> route/service -> memory service -> Redis connection pool`.

The Redis server remains a separately managed process. No request creates a new connection pool; all requests served by one FastAPI worker reuse the worker's pool.

## Failure handling

- A Redis command failure in conversation memory is caught as `RedisError` and falls back to PostgreSQL history.
- A failed readiness PING returns HTTP 503.
- Redis startup failure prevents the application from starting, because the current project treats Redis as a required dependency for readiness. The chat path still has command-level degradation after startup.

## Testing

- Lifespan tests use a real Redis client only inside their own application lifecycle.
- Service tests pass a fake or mocked Redis client explicitly; they do not share a module-level asynchronous socket.
- Keep one real Redis integration test for list order, trimming, and TTL.
- Add a degradation test that makes Redis read raise `RedisError` and asserts PostgreSQL history is used.

## Scope

This refactor changes resource ownership and dependency flow only. It does not add Redis retries, rate limiting, queueing, streaming, or long-term memory.
