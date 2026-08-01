# Interview review queue design

## Goal

Implement the first product-differentiated asynchronous capability: an interview-session review job that can be queued immediately and processed by a Worker without holding an HTTP connection open.

## Responsibilities

- PostgreSQL is the source of truth for each job's owner, conversation/session references, state, timestamps, error, and final review result.
- Redis Stream is a dispatch signal, not the durable source of job truth.
- A Worker consumes jobs through a Redis Stream Consumer Group and acknowledges a message only after the PostgreSQL job reaches a terminal state.

## Job contract

`interview_session_review` represents analysis of a completed mock-interview session. The first implementation stores references only: `task_id`, `user_id`, `conversation_id`, and `session_id`. It does not yet call an LLM or define the final scoring rubric.

States are `queued -> running -> completed | failed`.

## Delivery semantics

Redis Streams provides at-least-once delivery. After reading a message, a Worker must use PostgreSQL state to avoid reprocessing a terminal task. It acknowledges (`XACK`) only after a terminal state is persisted. A crashed Worker leaves the message pending for future recovery.

## HTTP contract

Creating a review returns HTTP 202 with `task_id` and `status="queued"`. A separate status endpoint returns the owner-visible task state and, when complete, its result.

## Scope limits

This slice excludes LLM scoring, retries, stale-message reclaiming, cancellation, scheduled jobs, dead-letter queues, and multi-worker autoscaling. The Worker handler is a deterministic placeholder so queue semantics can be tested first.
