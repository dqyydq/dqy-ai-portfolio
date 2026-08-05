# Unified Realtime Event Transport Design

## Goal

Add realtime delivery without duplicating business semantics:

- Chat LLM tokens stream through Server-Sent Events (SSE).
- Interview-review task progress and completion are pushed through WebSocket.
- Both transports use the same versioned event envelope.

PostgreSQL remains the source of truth for messages and review tasks. Redis Pub/Sub is transient delivery only; clients recover missed events by reading existing REST resources.

## Event protocol

Every realtime payload is JSON:

```json
{
  "version": 1,
  "type": "message.delta",
  "conversation_id": "uuid-or-null",
  "task_id": "uuid-or-null",
  "data": {},
  "occurred_at": "ISO-8601 timestamp"
}
```

Event types:

- `message.started`, `message.delta`, `message.completed`, `message.failed`
- `review.status`, `review.completed`, `review.failed`
- `error`

`message.completed` includes the persisted assistant message ID. `review.completed` includes the task ID; its full Markdown result remains available through `GET /interview-reviews/{task_id}`.

## SSE chat stream

`POST /conversations/{conversation_id}/messages/stream` accepts the existing message body and Bearer authorization. It performs the same owner check and rate-limit check as the non-stream endpoint.

The service writes the user message before streaming. It emits deltas from the provider, accumulates the full assistant response, persists the assistant message only after a successful complete stream, updates Redis conversation memory, then emits `message.completed`.

On provider failure it emits `message.failed`; no partial assistant message is persisted. The existing non-stream endpoint remains for compatibility.

SSE response content type is `text/event-stream`; each event uses `event: <type>` and `data: <JSON>`.

## WebSocket event channel

`GET /ws/events?token=<JWT>` upgrades to WebSocket after JWT validation. Browser WebSocket APIs cannot set the Authorization header, so the token is limited to connection setup and never written to logs.

The API process subscribes each connection to a user-owned Redis Pub/Sub channel:

```text
agent:realtime:user:v1:{user_id}
```

No client can choose another user's channel. The server forwards only valid shared-envelope events. Ping/pong or application keepalive messages retain the connection; invalid events and malformed authentication close the socket.

## Publisher boundary

The interview-review Worker publishes `review.status` after committed transitions (`running`, `completed`, `failed`). The chat service publishes its message lifecycle events locally to SSE; it may also publish terminal events to the user channel so other tabs stay synchronized.

Redis Pub/Sub has at-most-once delivery. On reconnect, the frontend refetches conversations/messages and review status. This is intentionally not a replacement for Redis Streams or PostgreSQL.

## Frontend behavior

- Use `fetch()` and `ReadableStream` to consume the authenticated POST SSE endpoint; `EventSource` is not used because it cannot attach the Bearer header.
- Render deltas into one optimistic assistant message. On `message.completed`, invalidate/refetch messages to reconcile the persisted ID.
- Open one authenticated WebSocket after login. Dispatch shared event types to React Query invalidations and active review UI.
- Reconnect with bounded exponential backoff. On reconnect, refetch active resources rather than assuming Pub/Sub replay.

## Error and security behavior

- Invalid/missing SSE token: normal HTTP `401` before stream starts.
- Invalid WebSocket token: close with `4401`.
- Redis Pub/Sub failure: WebSocket sends a typed `error` then closes; REST endpoints remain usable.
- The LLM API key and JWT are never emitted in event payloads or logs.

## Tests

- SSE service: owner isolation, rate-limit placement, ordered started/delta/completed events, persisted assistant result, and provider failure.
- WebSocket: valid user connection, invalid token close, user-channel isolation, and reconnect-resource fetch contract.
- Worker: committed status transition occurs before publishing terminal event.
- Frontend: parser/dispatcher tests or build verification for stream and socket handling.

## Non-goals

- No exactly-once delivery or Pub/Sub replay.
- No cross-instance WebSocket session registry beyond Redis Pub/Sub.
- No tool-call streaming, binary payloads, presence indicators, or collaborative editing.
