# Day 6 Learning Record: Rate Limit and Task Queue

## Day Checklist

- [x] Define authenticated chat rate-limit policy and Redis key contract
- [x] Implement an atomic fixed-window rate-limit dependency
- [x] Add limit, TTL, and concurrency-focused tests
- [x] Define the task queue boundary and job state model
- [x] Implement the smallest queue/worker experiment
- [ ] Interview review and Git closeout

## Realtime Transport Extension

### Task 6.10: Unified realtime event contract

- Status: in progress
- Scope: Learn the division between SSE token streaming and WebSocket task events, then define one versioned JSON event envelope shared by both transports.
- Out of scope: Implementing an endpoint, Redis Pub/Sub, reconnect logic, and frontend rendering before the event contract is understood.
- Acceptance criteria: Can explain why SSE is selected for a one-way token stream, why WebSocket is selected for Worker-originated status notifications, and write an event envelope containing type, ownership identifiers, data, and timestamp.
- Evidence: Approved design: `docs/superpowers/specs/2026-08-02-realtime-event-transport-design.md`.
- Next task: Learner implements the event dataclass and event-type enum in a small isolated service module.

### Task 6.11: User-isolated realtime publisher

- Status: completed
- Scope: Publish the shared event envelope to a user-owned Redis Pub/Sub channel without coupling publishing to WebSocket delivery.
- Out of scope: WebSocket routing, event replay, and Redis Streams task dispatch.
- Acceptance criteria: A publisher derives the channel from a server-provided user UUID and emits JSON produced by `RealtimeEvent.to_payload()`.
- Evidence: Learner implemented `backend/app/realtime/publisher.py`. Real Redis integration test `python -m pytest -q tests/test_realtime_publisher.py` -> `1 passed in 0.27s`.
- Next task: Run the Pub/Sub experiment and then build the authenticated WebSocket subscriber.

### Task 6.12: Authenticated WebSocket subscriber

- Status: completed
- Scope: Authenticate a WebSocket using JWT, derive its Redis Pub/Sub channel from the resolved user, and forward shared-envelope JSON events.
- Out of scope: Client-originated WebSocket commands, replay, reconnect UI, and task-state publication.
- Acceptance criteria: Missing token closes with `4401`; an authenticated connection receives only a message published to its user-owned channel.
- Evidence: Learner implemented `backend/app/realtime/websocket_auth.py` and `backend/app/api/realtime.py`, then registered the router. `python -m pytest -q tests/test_realtime_publisher.py tests/test_realtime_websocket.py` -> `3 passed in 3.19s`.
- Next task: Publish Worker task transitions only after the matching PostgreSQL commit.

### Task 6.13: Worker realtime status publication

- Status: completed
- Scope: Publish `review.status`, `review.completed`, and `review.failed` after their matching task-state commits, then forward them through the user-isolated realtime channel.
- Out of scope: Event replay, retry/reclaim, and frontend reconnect handling.
- Acceptance criteria: A task publishes `running` before `completed`; publication failure does not roll back a committed task state; Stream acknowledgement remains after successful processing.
- Evidence: Learner wired `redis_client` into `process_interview_review_task()` and added post-commit event calls. Worker integration test subscribes to the user channel and verifies event order and payload statuses. `python -m pytest -q tests/test_interview_review_task_service.py tests/test_realtime_websocket.py` -> `5 passed in 2.79s`.
- Next task: Add an authenticated SSE endpoint for one-way LLM token streaming.

### Task 6.14: Authenticated SSE chat stream

- Status: completed
- Scope: Save user messages, stream normalized token events through `text/event-stream`, persist only a completed assistant response, and retain the existing non-stream route for compatibility.
- Out of scope: Browser parsing, terminal chat Pub/Sub events, cache-after-stream, and provider cancellation.
- Acceptance criteria: SSE emits started/delta/completed in order; a failed or empty stream does not create a partial assistant row; the same Redis Memory and project-interview Day instruction are used as the non-stream path.
- Evidence: Learner implemented `stream_message_generation()` and `POST /conversations/{conversation_id}/messages/stream`. The integration test verifies two deltas and final assistant persistence. `python -m pytest -q tests/test_conversation_sse_api.py tests/test_conversation_api.py` -> `8 passed in 7.86s`.
- Next task: Parse authenticated POST SSE in the frontend and render one incrementally updated assistant message.

### Task 6.15: Realtime frontend transport

- Status: completed implementation; runtime restart and manual browser experiment pending.
- Scope: Parse authenticated POST SSE with `fetch`/`ReadableStream`, progressively render one assistant message, subscribe to user WebSocket events, and reconnect with bounded exponential backoff.
- Out of scope: Browser-side event persistence, a global notification center, and token-by-token cache writes.
- Acceptance criteria: Frontend TypeScript understands the shared event envelope; SSE deltas update one message; WebSocket task completion invalidates the relevant review query; Vite proxies WebSocket upgrade requests.
- Evidence: Added `RealtimeEvent` TypeScript types, SSE parser, streaming composer state, WebSocket event handling, reconnect logic, and `/ws` Vite proxy. `npm run build` -> successful. Realtime backend suite: `7 passed in 3.48s`.
- Next task: Restart local processes, perform a browser SSE/WebSocket experiment, then run full regression and Git closeout when requested.

## Project Interview LLM Extension

- Status: completed implementation and experiment; Git closeout pending.
- Added a dedicated `project_interview` conversation mode with a mutable current `learning_day` and an owner-only Day rebind endpoint.
- Each `InterviewReviewTask` snapshots `learning_day` at creation. A later rebind cannot change an existing queued or completed review's intended scope.
- The Worker now reads persisted PostgreSQL messages, extracts the matching Day section from `AI-Agent-Platform-Redis-Learning.md`, builds a Markdown-review prompt, and calls the configured OpenAI-compatible DeepSeek client from the separate Worker process.
- Real experiment: a temporary Day 6 conversation was queued on a temporary Redis Stream, processed with the configured DeepSeek API, and persisted as `STATUS=completed` with Markdown sections beginning `## Summary`, `## What You Understand`, and `## Corrections`. Temporary Stream and database rows were removed after the experiment.
- Regression evidence: `python -m pytest -q` -> `48 passed in 17.72s`; `npm run build` -> successful TypeScript/Vite production build. The only backend warning is the existing Starlette/TestClient deprecation warning.
- Limitation: the temporary terminal experiment's Chinese message was garbled by PowerShell's inline-script encoding. Browser requests are JSON/UTF-8 and do not use this input path. The next production improvement is a dedicated Worker process/service plus pending-message recovery and an Outbox re-dispatcher.

## Task Log

### Task 6.16: Redis and PostgreSQL responsibility boundary

- Status: completed
- Scope: Explain which Redis-backed capabilities may degrade after Redis data loss and which business facts must remain PostgreSQL-authoritative.
- Out of scope: Redis high availability or an Outbox implementation.
- Acceptance criteria: Can distinguish a recoverable Redis acceleration/dispatch loss from irreversible business-data loss.
- Evidence: Learner identified cache, rate limit, and Worker dispatch as Redis-backed concerns that may degrade, while chat messages and other database business facts must not depend on Redis. Clarification: a Redis Stream dispatch signal may be lost, but the PostgreSQL `queued` review task remains recoverable; a later scan or Outbox must re-dispatch it.
- Next task: Redis core data structures and their project mappings.

### Task 6.17: Redis String rate-limit interview review

- Status: completed
- Scope: Compare a Redis String counter with a naïve PostgreSQL count-based rate-limit implementation.
- Out of scope: Replacing the existing Lua fixed-window implementation.
- Acceptance criteria: Can name latency/write-pressure, short data lifecycle, and check-then-write race reasons.
- Evidence: Learner identified Redis as lower-overhead for this hot path and correctly identified the concurrent `SELECT` race. Correction added: a rate-limit counter has no durable business value after its time window, so Redis TTL removes it automatically; PostgreSQL would need bucket rows, cleanup, indexes, and sustained write load. A SQL atomic update can avoid the race, but it is still a worse fit for this high-frequency ephemeral counter.
- Next task: Explain why `INCR` plus `EXPIRE` needs a Lua atomic boundary.

### Task 6.18: `INCR` and `EXPIRE` atomicity boundary

- Status: completed
- Scope: Distinguish Redis single-command atomicity from the application-level two-command failure window.
- Out of scope: Sliding-window rate limiting and distributed transactions.
- Acceptance criteria: Can explain why command serialization prevents lost increments but does not make `INCR` plus conditional `EXPIRE` one atomic unit.
- Evidence: Learner correctly recognized the need for an atomic boundary. Clarification added: concurrent `INCR` commands themselves are serialized by Redis, so the critical failure is `INCR` returning `1`, followed by process/network failure before `EXPIRE`. The newly created key then has no TTL and later requests do not repair it because their counts are no longer `1`. The existing Lua script executes increment, first-write expiry, and TTL read as one Redis operation.
- Next task: Learn Redis List through conversation-memory operations.

### Task 6.19: Redis List conversation window

- Status: completed
- Scope: Model the latest five conversation messages as a Redis List ordered from oldest to newest.
- Out of scope: Semantic long-term memory and vector retrieval.
- Acceptance criteria: Can choose append, trim, and read commands that preserve chronological LLM input order.
- Evidence: Learner chose `RPUSH`, `LTRIM key -5 -1`, and `LRANGE`. Clarification added: after trimming the key to five items, use `LRANGE key 0 -1` to read the complete bounded List in old-to-new order; `LRANGE key -5 -1` is equivalent only because the preceding trim guarantees at most five values. The production append pipeline combines append, trim, and expiry.
- Next task: Compare Redis List with Redis Stream and explain why the Worker queue cannot use the memory List.

### Task 6.20: Redis List versus Stream queue semantics

- Status: completed
- Scope: Compare bounded conversation-memory Lists with Worker dispatch Streams through acknowledgement, crash recovery, and multi-consumer behavior.
- Out of scope: Kafka/RabbitMQ comparison and production retry policy.
- Acceptance criteria: Can state why a List pop risks task loss and why a Stream Consumer Group keeps unacknowledged work recoverable.
- Evidence: Learner identified that acknowledgement before knowing whether execution succeeded or failed is incorrect. Clarification added: `XACK` removes a delivery from the Consumer Group Pending Entries List rather than deleting the Stream history. It must follow the committed PostgreSQL terminal state. A crash after `XACK` but before commit makes normal Stream recovery impossible; a crash after commit but before `XACK` may redeliver the task, which is acceptable only with idempotent task handling.
- Next task: Learn cache-aside as the Redis cache pattern used for conversation and LLM caching.

### Task 6.21: Cache-aside read and refill path

- Status: completed
- Scope: Explain why a cache miss must both return authoritative data and repopulate Redis.
- Out of scope: Write-through, write-behind, and stale-data invalidation.
- Acceptance criteria: Can state the hit path, miss path, and the practical value of the refill.
- Evidence: Learner correctly explained that omitting a Redis refill makes the cache ineffective for subsequent requests. Clarification added: refill turns a first expensive PostgreSQL/LLM read into later low-latency hits and allows hot cache keys to recover naturally after eviction or Redis restart.
- Next task: Identify cache penetration, breakdown, and avalanche from failure timelines.

### Task 6.22: Cache penetration diagnosis

- Status: completed
- Scope: Identify requests for nonexistent resources that repeatedly bypass both cache and database lookup.
- Out of scope: Hot-key expiry and fleet-wide expiry failures.
- Acceptance criteria: Can distinguish penetration from breakdown and avalanche using the request target's existence.
- Evidence: Learner correctly identified high-concurrency requests for a nonexistent `conversation_id`, absent from both Redis and PostgreSQL, as cache penetration.
- Next task: Design bounded negative-cache and input/authorization defenses for nonexistent resources.

### Task 6.23: Cache breakdown and hot-key distinction

- Status: completed
- Scope: Identify one highly requested cache key expiring and causing concurrent expensive origin calls.
- Out of scope: Large-key memory problems and multi-key avalanche.
- Acceptance criteria: Can distinguish a hot key (high access frequency) from a big key (large value/cardinality) and name a breakdown mitigation.
- Evidence: Learner correctly identified the simultaneous origin calls after one popular LLM cache key expires as cache breakdown. Clarification added: a hot key is accessed very frequently; it need not hold a large value. A mutex/single-flight rebuild or short stale-while-revalidate period prevents every concurrent caller from regenerating the same expensive response.
- Next task: Identify cache avalanche and explain TTL jitter.

### Task 6.24: Cache avalanche and TTL jitter

- Status: completed
- Scope: Explain synchronized multi-key expiry, source-system overload, and expiry-time spreading.
- Out of scope: Redis Cluster failures and capacity planning.
- Acceptance criteria: Can distinguish jitter's reduced synchronized misses from a guarantee of cache hits, and separate avalanche mitigation from hot-key breakdown protection.
- Evidence: Learner correctly identified cache avalanche and recognized that TTL jitter cannot eliminate eventual misses. Clarification added: jitter reduces the number of keys missing at the same instant; it does not prevent each key from eventually expiring. Hot-key locking addresses single-key breakdown, while jitter, prewarming, and source protection address multi-key avalanche; production systems can combine them.
- Next task: Learn Redis expiration and memory eviction policies, including why eviction is not the same as TTL expiry.

### Task 6.25: TTL expiry versus memory eviction

- Status: completed
- Scope: Distinguish intentional per-key expiry from Redis max-memory eviction and select policies by data criticality.
- Out of scope: Redis memory sizing calculations.
- Acceptance criteria: Can explain why LRU is useful for caches but inappropriate as a blanket policy for Streams or coordination state.
- Evidence: Learner selected least-recently-used data, a common cache choice. Clarification added: `allkeys-lru`/`allkeys-lfu` may protect cache hit rate, while `volatile-ttl` favours keys closest to their intended expiry. Redis queues/Streams must not share an eviction-enabled cache instance; use a separate resource or `noeviction` capacity boundary because evicting unprocessed dispatch data is a delivery failure.
- Next task: Compare common eviction-policy choices for cache-only and mixed criticality Redis workloads.

### Task 6.26: LRU versus LFU cache policy selection

- Status: completed
- Scope: Select an eviction policy for a cache with a few repeatedly accessed LLM prompts and many one-off prompts.
- Out of scope: Exact Redis LFU counter internals and memory sizing.
- Acceptance criteria: Can distinguish recency from frequency and select the policy that preserves durable hot entries.
- Evidence: Learner initially selected LRU. Correction added: `allkeys-lfu` better fits the stated repeated-hot-question distribution because it retains frequently used entries; LRU can retain a recently used one-off key while evicting an older but repeatedly valuable key. Both policies are approximate in Redis and should be chosen from observed traffic rather than assumed universally.
- Next task: Learn Hash and its boundary with String/JSON cache values.

### Task 6.27: Redis Hash versus String cache values

- Status: completed
- Scope: Choose a value type for complete LLM-answer caching and distinguish it from independently mutable object fields.
- Out of scope: RedisJSON module and application-schema design.
- Acceptance criteria: Can select String for an atomic response value and Hash for independently updated small fields.
- Evidence: Learner correctly selected String for a complete LLM answer. Clarification added: whole-response cache reads/writes are unit operations, so a Hash adds unnecessary field-level structure; Hash is appropriate when fields such as profile settings change independently.
- Next task: Learn Set and ZSet through deduplication, membership, and ranking queries.

### Task 6.28: Redis Set membership and deduplication

- Status: completed
- Scope: Model whether a user has answered a question using unique members rather than an ordered history.
- Out of scope: Answer-history ordering and score ranking.
- Acceptance criteria: Can distinguish duplicate behavior, order, and membership-query complexity for List and Set.
- Evidence: Learner correctly identified Set's natural de-duplication and suitability for repeated membership checks. Clarification added: both List and Set can store meaningful identifiers; List is ordered and permits duplicates, while Set is unordered and unique. `SISMEMBER` is expected O(1), whereas List membership requires O(N) scanning; memory footprint is not guaranteed smaller because Set has its own structural overhead.
- Next task: Learn ZSet score ordering and why it differs from a Set.

### Task 6.29: ZSet activity-ranking score design

- Status: completed
- Scope: Choose an ordering score for a seven-day active-user leaderboard and expose the time-window requirement.
- Out of scope: Exact online-duration telemetry implementation.
- Acceptance criteria: Can distinguish recency ranking from accumulated-activity ranking and state how stale activity leaves a rolling window.
- Evidence: Learner selected online duration, valid when active means cumulative online time in the last seven days. Clarification added: a single continually accumulated ZSet score cannot represent a rolling seven-day total by itself; use daily buckets plus aggregation/expiry, scheduled recomputation, or a bounded window design. If the product instead means most recently active, the score should be a Unix timestamp.
- Next task: Learn Redis persistence and the RDB/AOF tradeoff.

### Task 6.30: RDB and AOF durability tradeoff

- Status: completed
- Scope: Choose a Redis persistence mechanism when restart recovery should lose as few writes as practical.
- Out of scope: Redis backup topology and exact production configuration.
- Acceptance criteria: Can distinguish snapshot loss windows from append-log durability and name the latency tradeoff.
- Evidence: Learner selected AOF (written as AOP). Clarification added: RDB saves periodic point-in-time snapshots and can lose writes since the last snapshot; AOF appends write operations. `appendfsync everysec` commonly trades up to about one second of write loss for reasonable throughput, while `always` reduces the loss window at higher fsync latency. Cache data may deliberately use no persistence; Stream dispatch persistence does not replace PostgreSQL task authority and recovery.
- Next task: Compare Redis replication, Sentinel, and Cluster as separate availability/scaling mechanisms.

### Task 6.31: AOF fsync policy tradeoff

- Status: completed
- Scope: Explain why the most durable AOF fsync mode is not automatically the production default.
- Out of scope: Filesystem and storage-device benchmarking.
- Acceptance criteria: Can distinguish `always`, `everysec`, and `no` in terms of write latency and expected loss window.
- Evidence: Learner recognized that `appendfsync always` is not necessarily best and requested explanation. Explained that `always` waits for disk synchronization on every write, increasing latency and reducing throughput; `everysec` batches the durability boundary around once per second; `no` delegates timing to the operating system and allows a wider loss window.
- Next task: Compare Redis replication, Sentinel, and Cluster as separate availability/scaling mechanisms.

### Task 6.32: Replication and Sentinel failover boundary

- Status: completed
- Scope: Distinguish data replication from automatic primary-failure detection and promotion.
- Out of scope: Redis Cluster slot migration.
- Acceptance criteria: Can state that replicas do not self-promote merely because the primary is unavailable.
- Evidence: Learner correctly answered that a replica will not automatically become primary without Sentinel (or another orchestrator). Clarification added: Sentinel reaches a monitored/quorum-backed failure decision, elects a Sentinel leader, promotes a replica, reconfigures remaining replicas, and requires clients to discover the new primary. Replication is asynchronous by default, so failover can still lose writes not yet replicated.
- Next task: Explain why Sentinel needs a quorum and why a single Sentinel is not high availability.

### Task 6.33: Sentinel quorum and majority availability

- Status: completed
- Scope: Explain why a three-Sentinel deployment does not fail over with only one Sentinel remaining.
- Out of scope: Manual emergency promotion procedures.
- Acceptance criteria: Can connect quorum/majority loss to intentionally unavailable automatic failover.
- Evidence: Learner correctly concluded that automatic failover should not proceed because quorum is not met. Clarification added: in a normal three-Sentinel topology, one remaining Sentinel also lacks the majority required to authorize leader election/failover. This intentionally sacrifices automatic availability to avoid one isolated observer creating a split-brain risk.
- Next task: Learn Redis Cluster sharding, hash slots, and its separation from Sentinel.

### Task 6.34: Redis Cluster hash slots and multi-key locality

- Status: completed
- Scope: Explain deterministic key-to-node routing, why a multi-key command requires key locality, and the role of hash tags.
- Out of scope: Cluster provisioning and slot migration operations.
- Acceptance criteria: Can explain a `CROSSSLOT` rejection without treating Cluster as a distributed transaction system.
- Evidence: After the prerequisite sharding explanation, learner correctly explained that keys on different nodes require distributed/network coordination. Clarification added: atomic cross-slot execution would require Node A and Node B to coordinate commit, failure, and rollback decisions; Redis Cluster rejects this rather than implementing distributed transactions. Hash tags can co-locate deliberately related keys, but overusing one tag recreates a hot shard.
- Next task: Learn Redis distributed locks and why ownership tokens are mandatory.

### Task 6.35: Redis distributed-lock safety model

- Status: completed
- Scope: Learn atomic acquisition, lease expiry, ownership-token release, and the remaining stale-holder limitation.
- Out of scope: Adding a lock to the current conversation-scoped LLM cache or adopting Redlock.
- Acceptance criteria: Can describe `SET ... NX PX`, compare-and-delete release, and why a lease alone is not full correctness for externally visible writes.
- Evidence: Learner requested the prerequisite walkthrough, then confirmed understanding of the stale-owner timeline. Learned that a unique token identifies lock ownership and compare-and-delete prevents a request whose lease expired from deleting a newer holder's lock. The minimum pattern is `SET key token NX PX ttl` plus Lua compare-and-delete. A lease does not make external side effects exactly once; use fencing tokens or database constraints when stale holders could cause irreversible writes.
- Next task: Compare Pipeline, MULTI/EXEC, and Lua atomicity for Redis multi-command work.

### Task 6.36: Pipeline, transaction, and Lua boundary

- Status: completed
- Scope: Select the appropriate Redis batching/atomicity mechanism for conversation-memory writes and fixed-window rate limits.
- Out of scope: General-purpose Redis scripting framework.
- Acceptance criteria: Can distinguish network batching from multi-step business atomicity and identify a result-dependent branch.
- Evidence: Learner correctly identified pipeline's network-round-trip benefit for append/trim/TTL and the need for a stronger boundary around rate-limit failure/concurrency cases. Clarification added: `INCR` is already a single atomic Redis command; Lua makes the compound `INCR -> if first count then EXPIRE -> TTL` business rule atomic. `MULTI/EXEC` serializes queued commands but does not let a client-side conditional branch safely use an intermediate result without reopening the gap.
- Next task: Compare Redis Pub/Sub and Streams delivery semantics.

### Task 6.37: Redis Pub/Sub ephemeral delivery

- Status: completed
- Scope: Determine whether an offline browser can receive a previously published Worker status event.
- Out of scope: Implementing an event-replay service.
- Acceptance criteria: Can distinguish Pub/Sub's online fan-out from durable/replayable message delivery.
- Evidence: Learner correctly concluded that the notification cannot be automatically replayed. Clarification added: Pub/Sub drops a message whenever no active subscriber is listening, even if Redis and the Worker remain healthy; it has no acknowledgement, pending state, or history. In this project, PostgreSQL remains the durable review-task status source, so reconnecting UI queries it again while Pub/Sub/WebSocket only accelerates online updates.
- Next task: Compare the use of Pub/Sub versus Streams for the project's two message paths.

### Task 6.38: Streams dispatch versus Pub/Sub notification

- Status: completed
- Scope: Compare durability, acknowledgement, recovery, and source-of-truth requirements for Worker commands versus browser refresh notifications.
- Out of scope: Replacing either transport or adding event replay.
- Acceptance criteria: Can choose Streams for must-run work and Pub/Sub for lossy online fan-out with a durable database fallback.
- Evidence: Learner requested a code-level walkthrough and then confirmed understanding. Mapped the status-notification chain: post-commit Worker publisher -> user-scoped Redis Pub/Sub channel -> authenticated WebSocket forwarder -> frontend query invalidation. Clarification added: losing this notification only delays UI refresh because PostgreSQL owns the review result; losing a Stream dispatch could prevent required work and therefore needs acknowledgement/recovery semantics.
- Next task: Learn Hot Key and Big Key diagnosis and mitigation.

### Task 6.39: Hot Key and Big Key diagnosis

- Status: completed
- Scope: Diagnose an unbounded conversation-memory List read in full for every LLM call.
- Out of scope: Redis Cluster resharding and exact memory profiling commands.
- Acceptance criteria: Can identify size-driven risk separately from access-frequency-driven risk.
- Evidence: Learner correctly identified the untrimmed five-million-item List as a Big Key. Clarification added: full `LRANGE 0 -1` produces a large response, consumes memory/network, and can monopolize Redis command processing; it becomes a Hot Key only if it also receives unusually frequent access. The existing bounded `LTRIM` window prevents this failure class.
- Next task: Learn safe production key scanning and why `KEYS` is dangerous.

### Task 6.40: Safe key scanning and Big Key deletion

- Status: completed
- Scope: Choose non-blocking patterns for inspecting a large keyspace and deleting a very large key.
- Out of scope: A live production cleanup operation.
- Acceptance criteria: Can distinguish `KEYS` from cursor-based `SCAN`, and `DEL` from background-freeing `UNLINK`.
- Evidence: Explained that `KEYS *` performs a blocking full scan and should be replaced by cursor-based `SCAN` for operations. Learner requested the deletion prerequisite explanation; learned that synchronous `DEL` of a 2 GB structured key can block Redis while reclaiming memory, whereas `UNLINK` makes the key logically unavailable quickly and delegates memory freeing to background work.
- Next task: Explain Redis client pooling and lifecycle ownership in FastAPI.

### Task 6.41: Redis client pool and FastAPI lifecycle

- Status: completed
- Scope: Explain why a Redis client/pool belongs to process lifespan rather than individual request handlers.
- Out of scope: Exact production pool-size tuning.
- Acceptance criteria: Can describe connection reuse and shutdown ownership.
- Evidence: Learner correctly identified connection-pool reuse rather than per-request client construction. Clarification added: `redis.asyncio.Redis` uses a pool; the application creates one shared client during FastAPI lifespan, each operation borrows a connection as needed, and shutdown closes the client/pool. Pub/Sub uses a dedicated subscribed connection and should not be treated like ordinary pooled command traffic.
- Next task: Learn Redis observability and the slowlog / latency diagnosis boundary.

### Task 6.42: Redis latency diagnosis and Slow Log

- Status: completed
- Scope: Identify server-side slow Redis commands separately from network and application latency.
- Out of scope: Live production monitoring configuration.
- Acceptance criteria: Can name `SLOWLOG`, relevant `INFO` sections, and the risk of `MONITOR`.
- Evidence: Learner requested the prerequisite explanation. Learned that `SLOWLOG GET` exposes commands whose Redis-server execution exceeds the configured threshold but excludes client/network latency; `INFO memory`, `INFO clients`, and `INFO stats` complete the first diagnostic pass. `MONITOR` is unsuitable for casual production diagnosis because it emits all commands and can add load/expose data.
- Next task: Diagnose cache-hit-rate decline by classifying missing keys.

### Task 6.43: Cache hit-rate and eviction diagnosis

- Status: completed
- Scope: Explain cache misses caused by normal expiry, eviction, key-design changes, Redis lifecycle changes, and low request reuse.
- Out of scope: Automatic cache-autoscaling implementation.
- Acceptance criteria: Can distinguish `expired_keys` from `evicted_keys` and avoid blindly treating memory expansion as the first fix.
- Evidence: Learner requested clarification of `evicted_keys`. Learned that `expired_keys` counts intended TTL expiry, while `evicted_keys` counts max-memory-policy removals. Sustained eviction signals memory pressure, but diagnosis must first check Big Keys/unbounded collections, TTL coverage, cache value, workload shape, and cache-versus-Stream separation before choosing expansion or policy changes.
- Next task: Learn cache write consistency strategies and the update/delete-cache ordering tradeoff.

### Task 6.44: Cache write consistency and write-behind risk

- Status: completed
- Scope: Choose a safe update order for cached database facts and reject unsafe write-behind use for critical records.
- Out of scope: Implementing a cache invalidation subsystem.
- Acceptance criteria: Can explain `DB first -> delete cache`, its eventual-consistency boundary, and why an asynchronous cache-to-database write is unsafe for balances/orders.
- Evidence: Learner correctly identified data loss when cache failure occurs before asynchronous database persistence. Clarification added: with write-behind, an acknowledged client request can disappear on Redis crash, queue loss, or failed async worker; ordering and duplicate retries also complicate balances/orders. Use a database transaction, constraints, idempotency, and durable outbox/reconciliation where external side effects are involved.
- Next task: Compare Redis MULTI/EXEC with PostgreSQL transactions and identify rollback limitations.

### Task 6.1: Define chat rate-limit contract

- Status: completed
- Scope: Limit authenticated message-generation requests per user in a fixed time window using Redis, and define the API response when the limit is exceeded.
- Out of scope: IP-based limits, distributed locks, sliding-window algorithms, queue workers, retries, and background jobs.
- Acceptance criteria: Can state the resource being protected, key ownership, fixed-window boundary, HTTP status/headers, and why increment plus initial TTL must be atomic.
- Evidence: Implemented `build_rate_limit_key()` and `check_message_rate_limit()` in `backend/app/services/rate_limit_service.py`. A real Redis Lua-script test verifies the first request TTL, ten allowed requests, an eleventh denied request, and per-user isolation: `python -m pytest -q tests/test_rate_limit_service.py` -> `2 passed in 0.18s`.
- Next task: Integrate a FastAPI dependency that maps allowed, denied, and Redis-failure results to HTTP behavior.

### Task 6.2: HTTP rate-limit dependency

- Status: completed
- Scope: Apply the user-owned limit only to message generation and return the documented 429/503 behavior and headers.
- Out of scope: IP limits, global middleware, all-endpoint limits, and task queues.
- Acceptance criteria: An allowed request proceeds; an exceeded request returns 429 without LLM generation; Redis error returns 503 without LLM generation.
- Evidence: Added `enforce_message_rate_limit()` and attached it to message generation. API tests verify that the eleventh request returns 429 with rate-limit headers and no eleventh LLM call; Redis `eval` failure returns 503 with zero LLM calls. `python -m pytest -q tests/test_rate_limit_service.py tests/test_conversation_api.py` -> `9 passed in 2.62s`.
- Next task: Interview review of the atomicity boundary before starting the separate task-queue module.

### Task 6.3: Rate-limit atomicity review

- Status: completed
- Scope: Explain why Lua is required for the chosen fixed-window algorithm and identify the remaining fixed-window burst behavior.
- Out of scope: Sliding window implementation and distributed locks.
- Acceptance criteria: Can distinguish atomic Redis execution from application-level concurrency and state the policy tradeoff.
- Evidence: Learner can explain the process-crash gap between Python `INCR` and `EXPIRE`, why the Lua script is the atomic Redis boundary, and the fixed-window boundary-burst tradeoff. The first version intentionally accepts short rollover bursts in exchange for simple, low-cost protection.
- Next task: Define the task-queue business boundary and delivery semantics.

### Task 6.4: Task queue boundary and delivery semantics

- Status: completed
- Scope: Identify which work must leave the HTTP request path, choose the minimal Redis queue primitive, and define what happens if a worker crashes after claiming work.
- Out of scope: Production PDF ingestion, retries, dead-letter queues, scheduled jobs, and multi-worker autoscaling.
- Acceptance criteria: Can distinguish request handling from background work and explain at-most-once versus at-least-once delivery for the chosen primitive.
- Evidence: Defined `interview_session_review` as the product-differentiated asynchronous job. Added PostgreSQL `InterviewReviewTask` with `queued -> running -> completed | failed` state model, owner and conversation references, result/error fields, and timestamps. Real PostgreSQL persistence test: `python -m pytest -q tests/test_interview_review_task.py` -> `1 passed in 0.55s`.
- Next task: Create a queued task transaction and publish its Redis Stream dispatch signal.

### Task 6.5: Queue publish boundary

- Status: completed
- Scope: Persist a queued task and publish a Redis Stream message containing its task ID; define the publish-failure consistency boundary.
- Out of scope: Worker consumption, retries, reclaiming pending messages, and final review generation.
- Acceptance criteria: Can state why PostgreSQL state is authoritative and identify the transaction/outbox limitation when PostgreSQL commit and Redis publish are separate systems.
- Evidence: Added `publish_interview_review_task()` using Redis `XADD`, then `create_and_publish_interview_review_task()` which commits the PostgreSQL `queued` row before publication. A real Stream test reads the exact returned message ID and verifies its `task_id` field. The service integration tests verify both successful dispatch and the failure path where Redis is unavailable but the committed task remains `queued`: `python -m pytest -q tests/test_interview_review_task_service.py` -> `3 passed in 0.75s`.
- Next task: Consume the dispatch with a Consumer Group and preserve PostgreSQL state before acknowledgement.

### Task 6.6: Consumer Group Worker skeleton

- Status: completed
- Scope: Create a Redis Streams Consumer Group and consume one new interview-review dispatch message without acknowledging it yet.
- Out of scope: PostgreSQL state transitions, acknowledgement, retry, and stale pending recovery.
- Acceptance criteria: Consumer Group creation is idempotent; a Worker can read one new message without affecting the formal queue in tests.
- Evidence: Added parameterized `ensure_consumer_group()` and `run_worker_once()`. The integration test uses a random Stream, group, and consumer; it verifies one new message is read once and a second read has no new message: `python -m pytest -q tests/test_interview_review_worker.py` -> `1 passed in 1.19s`.
- Next task: Implement task state transition and `XACK` ordering.

### Task 6.7: Worker state transition and acknowledgement

- Status: completed
- Scope: Read a Stream task, persist `queued -> running -> completed` through the placeholder handler, and acknowledge only after terminal state commit.
- Out of scope: Real LLM scoring, failed-task retry, stale pending reclaim, and cancellation.
- Acceptance criteria: An end-to-end task becomes completed in PostgreSQL and has no pending Stream message after successful Worker processing.
- Evidence: The integration test creates a random task and random Stream/Group, runs the Worker once, verifies result/timestamps/status, and checks Consumer Group pending count is zero: `python -m pytest -q tests/test_interview_review_task_service.py` -> `3 passed in 0.75s`.
- Next task: Add owner-authorized HTTP create/status contracts.

### Task 6.8: Interview review HTTP contract

- Status: completed
- Scope: Define task create and status APIs without running the Worker inside the HTTP process.
- Out of scope: Frontend polling UI, LLM scoring, and task cancellation.
- Acceptance criteria: Owners can enqueue a review and inspect its state; other users cannot access it.
- Evidence: Added `POST /interview-reviews/conversations/{conversation_id}` returning `202 Accepted`, owner-scoped `GET /interview-reviews/{task_id}`, and Pydantic request/response schemas. Integration tests verify owner read access, cross-user `404`, and the database-first failure boundary: a Redis publish failure returns `503`, includes the persisted task ID, and the owner can still read the task as `queued`. `python -m pytest -q tests/test_interview_review_api.py tests/test_interview_review_task_service.py tests/test_interview_review_worker.py` -> `6 passed in 10.76s` (one pre-existing Starlette/TestClient deprecation warning).
- Transaction and delivery boundary: PostgreSQL commit succeeds before Redis `XADD`; therefore the task is recoverable after a dispatch failure, but an automatic dispatcher/outbox is still required to publish it later.
- Next task: Run the full regression suite, then review at-least-once delivery and remaining production gaps before Git closeout.

### Task 6.9: Day 6 regression evidence

- Status: completed
- Scope: Run all existing backend tests after rate limiting and interview-review queue changes.
- Out of scope: Eliminating the third-party test-client deprecation warning or adding retry/outbox behavior.
- Acceptance criteria: All tests pass and the working diff has no whitespace errors.
- Evidence: `. .\\.venv\\Scripts\\Activate.ps1; $env:PYTHONPATH='backend'; python -m pytest -q; git diff --check` -> `48 passed in 17.11s`; `git diff --check` reported no errors. The only warning is Starlette's deprecation warning for the installed TestClient/httpx combination.
- Next task: Review the at-least-once delivery boundary, then commit only the Day 6 changes when requested.

## Problem Log

### Problem 6.1: Planning documents remain behind committed progress

- Observed at: 2026-08-01
- Symptom: `CLAUDE.md` and `docs/progress.md` identify an earlier Day despite committed Day 4 and Day 5 work.
- Reproduction or command: Compare the plan documents with commits `56db6c3` and `e8ade37`.
- Root cause: Day closeout records were written in `docs/dayN.md` but not safely synchronized into the legacy-encoded progress documents.
- Impact: Documentation cannot be used alone to infer the active Day.
- Resolution or next action: Use committed artifacts and current Day notes as the operational source of truth; fix legacy document encoding/synchronization during Day 6 closeout.
- Knowledge point: A learning plan is configuration. It needs a single authoritative update path to prevent state drift.
