# Streaming Markdown Reading Density Design

## Goal

Make assistant answers readable while they stream: Markdown should render as each SSE delta
arrives, and completed answers should use a compact, stable technical-reading rhythm.

## Scope

- Modify only `frontend/src/App.tsx` and `frontend/src/App.css`.
- Preserve the current API, SSE event format, data persistence, sidebar, composer, and user
  message bubble treatment.
- Do not add a Markdown editor, syntax-highlighting dependency, or model-output rewrite layer.

## Rendering behaviour

1. Assistant messages already saved in a conversation continue to render through
   `ReactMarkdown` with `remarkGfm`.
2. The pending assistant message uses that same renderer with the accumulated
   `streamedAssistantMessage` value. Each incoming `message.delta` therefore updates the
   rendered Markdown immediately.
3. Markdown syntax that is incomplete during generation is rendered according to the parser's
   current valid interpretation. When a closing delimiter arrives (for example a code fence),
   the next render adopts the complete structure automatically.
4. The existing thinking indicator remains visible until the first text delta arrives.

## Typography and spacing

- Preserve `white-space: pre-wrap` for user-authored messages only, so user-entered line
  breaks remain intentional.
- Assistant Markdown uses normal whitespace flow and compact block spacing.
- Headings have a smaller preceding gap than the current global treatment; paragraphs and
  lists use a consistent short vertical rhythm.
- List items remain legible, but nested paragraph margins do not multiply their height.
- Code blocks, tables, links, and block quotes retain their existing visual vocabulary.

## Responsive and accessibility requirements

- Existing mobile breakpoint behaviour remains intact with no horizontal page scroll.
- Long Markdown words and code remain safely wrapped or horizontally scrollable only inside
  their own code/table containers.
- No interaction controls change, so existing hover, focus, and keyboard behaviour is
  preserved.

## Verification

- Frontend production build passes with `npm run build`.
- Manually verify a streamed answer containing headings, ordered/unordered lists, inline code,
  and a fenced code block.
- Confirm an assistant response no longer creates oversized gaps from ordinary blank lines,
  while a user message still preserves deliberate newlines.
