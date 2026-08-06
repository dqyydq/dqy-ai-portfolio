# Private AI Studio Design

## Goal

Redesign the authenticated AI assistant into a refined private research studio while preserving every existing conversation, authentication, sign-out, personal DeepSeek API key, and message-sending behavior.

## Visual Direction

The page uses a quiet editorial workspace system: deep ink-navy for navigation, warm paper white for reading, mist-blue for selected and secure states, and a restrained sage detail for live status. It avoids neon, glass effects, generic dashboard cards, and decorative gradients.

## Layout

- A permanent dark left rail on desktop contains the owner mark, new conversation control, conversation history, and compact account/sign-out control.
- The main panel has a minimal top line showing the current private assistant context and an API-key configuration strip.
- No-message state: centered editorial welcome, short role description, and three real prompt suggestion buttons that place text into the composer.
- Message state: a narrow readable conversation rail with distinct user and assistant treatments.
- A paper-like composer is fixed to the bottom of the main panel, with a growing textarea, keyboard hint, and circular send control.
- Mobile collapses the rail into a compact top control without hiding the composer.

## Functionality

- New conversation clears the active conversation selection.
- Conversation buttons retain their existing selection behavior.
- API key save behavior remains unchanged; the UI only changes presentation.
- Prompt suggestions populate the draft field; sending still uses the existing API.
- Key, sign-out, and error states are visible and accessible.

## Files

- Modify `frontend/src/App.tsx` and `frontend/src/App.css` only for the application UI.
- Add this design spec and update `design-qa.md` after visual validation.
- No backend, API, schema, or route changes.

## Acceptance

1. At desktop width, the assistant reads as a deliberately designed private research workspace rather than a default admin panel.
2. At 320px, 375px, 414px, and 768px, no horizontal overflow occurs and primary controls remain visible.
3. Existing key management, conversation selection, send, and sign-out behavior remain functional.
