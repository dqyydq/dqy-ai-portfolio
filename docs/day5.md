# Day 5 Learning Record: Redis LLM Cache

## Day Checklist

- [ ] Define the LLM cache boundary and cache key contract
- [ ] Implement cache lookup, LLM fallback, and cache write
- [ ] Handle TTL, model/config versioning, and cache safety
- [ ] Add cache-hit, cache-miss, and failure-path tests
- [ ] Interview review and learning notes
- [ ] Git closeout

## Task Log

### Task 5.1: Define the LLM cache contract

- Status: completed
- Scope: Decide exactly what response may be reused, construct a deterministic key, and define safe inputs that must participate in key generation.
- Out of scope: Semantic cache, vector similarity, prompt caching offered by an LLM provider, streaming responses, rate limiting, and task queues.
- Acceptance criteria: Can distinguish LLM response caching from Day 4 conversation memory; can explain cache hit/miss and identify inputs that prevent an unsafe cross-request response reuse.
- Evidence: Implemented `build_llm_cache_key()` in `backend/app/services/llm_cache_service.py`. The key includes cache version, model, and ordered messages, canonicalizes JSON, and hashes it with SHA-256. `python -m pytest -q tests/test_llm_cache_service.py` returned `2 passed in 0.02s`.
- Next task: Add Redis cache read/write operations without changing the LLM call path yet.

### Task 5.2: Redis cache read/write contract

- Status: completed
- Scope: Define the cached value and implement small Redis read/write helpers with an explicit TTL.
- Out of scope: Wiring the cache into LLM generation, semantic similarity, and request coalescing.
- Acceptance criteria: A cache key can return one validated text response or a cache miss; writes have a bounded TTL.
- Evidence: Added `get_cached_llm_response()` and `cache_llm_response()` with a 3600-second TTL. The real Redis test verifies miss, independent writes, reads, and TTL: `python -m pytest -q tests/test_llm_cache_service.py` -> `3 passed in 0.27s`.
- Next task: Integrate cache-aside behavior into LLM generation.

### Task 5.3: LLM cache-aside integration

- Status: completed
- Scope: On an exact cache hit, return the stored LLM response without an upstream call. On a miss, call the LLM and cache a successful response.
- Out of scope: Caching failed/empty LLM responses, semantic cache, request coalescing, and streaming.
- Acceptance criteria: Cache hit avoids the LLM client; cache miss calls it once and writes the successful output; Redis errors fall back to a normal LLM call.
- Evidence: Added `CachedLLMClient` as a Redis-independent `LLMClient` decorator. Conversation generation passes `cache_scope=f"conversation:{conversation_id}"`. Unit tests verify hit avoids provider calls, miss calls the provider once and caches its answer, and Redis failure still returns a provider answer. Key tests verify scope isolation. Focused tests: `19 passed`; full suite: `36 passed`.
- Next task: Review cache safety, TTL/version invalidation, and remaining cache limits.

### Task 5.4: Cache safety and operational limits

- Status: completed
- Scope: Explain why failures are not cached, how TTL/version invalidate entries, and which cache stampede limitation remains.
- Out of scope: Implementing distributed locks, semantic caching, token accounting, or streaming.
- Acceptance criteria: Can describe the failure policy and identify the concurrent cache-miss limitation of cache-aside.
- Evidence: Established the policy: cache only successful non-empty provider responses; Redis failures bypass cache; TTL is 3600 seconds; version is in the key for immediate logical invalidation. Identified the remaining cache-stampede limitation: concurrent exact misses can independently call the provider because request coalescing is out of scope.
- Next task: Interview review and Day closeout.

### Task 5.5: Interview review

- Status: completed
- Scope: Explain exact-match caching, scope isolation, cache-aside, TTL/version invalidation, failure caching, and cache stampede using the project implementation.
- Out of scope: General Redis trivia unrelated to LLM Cache.
- Acceptance criteria: Can give a concise production explanation and state one remaining limitation.
- Evidence: Learner can explain conversation-scoped exact-match keys, cache-aside hit/miss behavior, 3600-second TTL, version invalidation, Redis/LLM failure policy, and cache-stampede as the known concurrency limit.
- Next task: Day closeout verification and optional Git commit.

## Interview Notes

### How the project designs LLM Cache

The project uses Redis for exact-match LLM response caching to reduce repeat provider calls, latency, and token cost. A key contains the cache version, model, complete ordered messages, and a conversation-scoped identifier. The canonical request payload is SHA-256 hashed, producing a fixed-length key without exposing prompt text.

`CachedLLMClient` implements cache-aside behavior. It returns a cached response on a hit. On a miss, it calls the provider-facing `LLMClient` once and caches only a successful, non-empty response for 3600 seconds. Redis read/write errors are logged and bypassed; provider errors, timeouts, 429s, 5xxs, and empty responses are never cached.

The scope includes `conversation_id`, so separate conversation threads cannot reuse each other's responses even if their text matches. `LLM_CACHE_VERSION` supports immediate logical invalidation: changing the version creates a fresh key namespace while old keys expire naturally.

Known limit: simultaneous exact cache misses can each call the provider, causing a cache stampede. A future Redis short lock or single-flight request coalescing can reduce duplicate calls, but is intentionally outside this first implementation.

## Problem Log

### Problem 5.2: LLM test double did not match the cache-aware interface

- Observed at: 2026-08-01
- Symptom: the conversation API failure-path test returned HTTP 500 instead of its expected 502 after cache scope was added.
- Reproduction or command: `python -m pytest -q tests/test_llm_cache_service.py tests/test_cached_llm_client.py tests/test_conversation_service.py tests/test_conversation_api.py`.
- Root cause: the API test's `FailingLLMClient.generate()` accepted only `history`; production now supplies `cache_scope` as a keyword argument, causing `TypeError` before the existing LLM error mapping could run.
- Impact: the test double no longer represented the production interface, hiding the intended 502 behavior.
- Resolution or next action: update every fake LLM implementation to accept the cache-aware argument, then rerun focused and full tests.
- Knowledge point: dependency injection makes test doubles part of an interface contract. Changing that contract requires updating success and failure fakes, not only production code.

### Problem 5.1: Learning progress documents are stale

- Observed at: 2026-08-01
- Symptom: `CLAUDE.md` and `docs/progress.md` still identify Day 2/Day 3 as current, while the committed Day 4 implementation and tests are complete.
- Reproduction or command: Read the two documents and compare with commits `56db6c3` and the latest passing test evidence.
- Root cause: Earlier Day progress was not synchronized back into both planning documents.
- Impact: A tool following documentation alone could restart an already completed Day.
- Resolution or next action: Use committed implementation and Day 4 evidence as the source of truth for this session; synchronize progress documents during Day 5 closeout.
- Knowledge point: Project documentation is operational state. Stale status can lead to incorrect engineering work just like stale configuration.
