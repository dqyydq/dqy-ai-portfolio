# Project Interview Conversation and LLM Review Design

## Goal

Turn the existing interview-review queue into a real learning feature. A user creates a dedicated project-interview conversation, answers questions in that conversation, and requests an asynchronous LLM review scoped to the currently selected project Day.

The source material is `AI-Agent-Platform-Redis-Learning.md`. The feature must not treat Redis as the source of truth and must not run provider calls in the HTTP request.

## User flow

1. The user creates a conversation with `mode="project_interview"` and an initial `learning_day`.
2. The user and LLM conduct normal question-and-answer turns in that conversation.
3. The user may update the conversation's current `learning_day` at any time.
4. The user requests a review for that conversation.
5. The API writes an `InterviewReviewTask` in PostgreSQL and publishes its ID to Redis Streams.
6. A Worker reads the task, reads the persisted conversation history and the matching Day material, then calls the configured OpenAI-compatible LLM.
7. The Worker writes a Markdown review result to PostgreSQL and acknowledges the Stream entry only after that terminal database state is committed.

## Data model

### Conversation

Add:

- `mode`: enum, `general` (default) or `project_interview`.
- `learning_day`: nullable integer. Required for `project_interview`, limited to the Days supported by the learning material.

The current binding is mutable. Updating it affects future prompts and future review requests only; it does not rewrite messages or existing tasks.

### InterviewReviewTask

Add:

- `learning_day`: non-null integer copied from `Conversation.learning_day` when the task is created.

This is an immutable task snapshot. A later conversation Day change cannot change how a queued, running, completed, or failed review is interpreted.

## API contract

- `POST /conversations/`: accepts optional `mode` and `learning_day`.
- `PATCH /conversations/{conversation_id}/learning-context`: owner-only; updates the Day only for a `project_interview` conversation.
- `POST /interview-reviews/conversations/{conversation_id}`: allowed only for a `project_interview` conversation with a valid current Day; returns `202 Accepted`.
- `GET /interview-reviews/{task_id}`: remains owner-only.

Validation errors use `422`; a missing or foreign conversation/task uses `404`; a Redis dispatch outage uses `503` while returning the persisted task ID as the existing contract specifies.

## Worker and LLM boundary

The Worker owns provider invocation. It constructs messages from:

- a system prompt defining the reviewer role and a strict Markdown output structure;
- the selected Day section from `AI-Agent-Platform-Redis-Learning.md`;
- persisted messages from the task's conversation, in chronological order and within an explicit bounded history limit;
- the task's immutable `learning_day` snapshot.

The prompt tells the LLM to grade only evidence in the conversation, identify misconceptions, provide concise standard answers, ask follow-up questions, and avoid claiming the learner said something they did not say.

The worker will construct its own `AsyncOpenAI`/`LLMClient` using settings; it cannot rely on FastAPI `app.state` because it is a separate process. LLM calls use the existing configured timeout. A review is not shared through the normal conversation cache because its task-specific history is private and its output is one-off.

On an LLM error, the Worker writes `failed` and a safe error message in PostgreSQL, then leaves the Stream message pending by not acknowledging it. Successful final state is committed before `XACK`.

## Consistency and delivery semantics

PostgreSQL is authoritative for conversations and task states. Redis Streams provides dispatch only.

The API commits the queued task before `XADD`. Therefore a Redis outage cannot lose the task, but it can leave a task queued and unpublished. This first version surfaces `503`; a later Transactional Outbox/re-dispatcher is required for automatic recovery.

Redis Consumer Groups provide at-least-once delivery. If a Worker commits completion but crashes before `XACK`, the message remains pending and can be delivered again. The state machine must make terminal tasks no-ops, preventing a duplicate provider call after recovery.

## Testing

- Schema/API: general versus project-interview creation, input validation, owner-only Day rebind, and rebind isolation.
- Task creation: review rejected for a general conversation; task snapshots the current Day.
- Worker: deterministic fake LLM verifies Day-scoped prompt construction, Markdown result persistence, LLM failure state, terminal-task idempotency, and ACK ordering.
- Existing Redis/PostgreSQL integration tests remain part of the full regression suite.

## Explicit non-goals

- No automatic re-dispatcher or Transactional Outbox yet.
- No stale pending-message reclaim, retry budget, cancellation, or dead-letter queue.
- No frontend review screen/polling implementation in this backend learning step.
- No semantic/vector retrieval; the Day scope and bounded conversation transcript are sufficient for the initial project learning material.
