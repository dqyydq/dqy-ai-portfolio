# SSE chat and resume correction design

## Goal

Keep the current private research studio visual language while restoring the original conversation system's SSE streaming behaviour. The product will not use WebSocket, learning workflows, or interview-review workflows. Public portfolio claims must be grounded exclusively in the supplied resume.

## Recruiter-first experience

- The public homepage is the primary experience: it must communicate role target, internship evidence, project ownership, and credible technical contribution before asking the visitor to log in.
- An interviewer or HR visitor must be able to assess the candidate without using the AI assistant. The assistant is an optional, authenticated deep-dive rather than a gate in the evaluation flow.
- Portfolio copy favours concise, verifiable statements of responsibility, mechanism, and outcome. It does not inflate responsibilities into unsupported backend, architecture, or management claims.
- GitHub and a clear contact action remain immediately discoverable; the phone number remains private.

## Chat behaviour

- Restore `POST /conversations/{id}/messages/stream` using `text/event-stream`.
- The stream emits `message.started`, repeated `message.delta`, then `message.completed`.
- The frontend creates a local user message and an empty assistant message before opening the stream; each delta updates the existing assistant bubble and is rendered as Markdown.
- The completed server message remains the source of truth and is persisted by the backend only after generation completes.
- When the first message creates a conversation, add that returned conversation directly to local state. Do not make the redundant conversation-list and message-list reads before streaming begins.
- Keep request authentication and rate limiting. Do not restore WebSocket or its realtime event routes.
- Surface stream and upstream-model failures in the current studio error treatment, without losing the user draft.

## Public portfolio content

- Do not show the phone number.
- Describe the owner as seeking a large-model application internship, not as a backend engineer or enterprise-architecture owner.
- Use resume-supported experience only: LianLian Pay large-model application R&D internship (2025.11-2026.02), Zhuojin Technology large-model application R&D internship (2025.07-2025.10), and the listed projects.
- The featured work will describe the AI financial-analysis assistant, Yishangbao registration Agent, ComfyUI AI storybook application, and Derm AI online consultation project using the resume's stated responsibilities and technologies.

## Navigation and scope

- Add a visible return-to-home button to the authenticated assistant studio. It clears only the current in-app view state and returns to the public portfolio; it does not sign the user out.
- Keep the existing research-studio layout and the current Markdown visual treatment. This work changes interaction, performance, navigation, and factual content rather than redesigning the interface.

## Verification

- Backend SSE test verifies event ordering and persistence of the final assistant message.
- Frontend production build must pass.
- Manual checks cover: creating the first conversation, incremental Markdown display, returning home, and the factual portfolio copy.
