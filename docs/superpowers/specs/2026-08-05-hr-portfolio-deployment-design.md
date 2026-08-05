# HR Portfolio and Safe Deployment Design

## Status

Awaiting user review before implementation.

## Goal

Turn the application into a recruiter-facing personal portfolio while preserving a separate, authenticated HTTP chat experience. Public visitors can evaluate Deng Quanyao's real AI application work without seeing private contact details, source code from internships, or any user API keys.

## Isolation

- The source worktree on `main` remains untouched after commit `083d830`.
- All work takes place on `deploy/hr-portfolio` in a separate Git worktree.
- The branch starts from the committed current application, then removes the out-of-scope learning, interview-review, background-worker, and WebSocket features.

## Public Portfolio

### Visual direction

- Follow the approved reference: warm off-white surface, ink navy type, generous whitespace, restrained blue-gray accents, and a subtle Chinese landscape treatment in the hero.
- Avoid exposing a portrait, phone number, email address, QQ number, QR code, or any other direct contact data.
- The sole public contact route is the GitHub profile: `https://github.com/dqyydq`.

### Information architecture

1. Hero: `邓权耀` and `大模型应用研发`, a concise business-delivery positioning statement, and a GitHub button.
2. Capability cards: LangGraph agent routing, FastAPI plus RAG retrieval, and financial document automation.
3. Selected case studies, presented as work cases rather than public repositories:
   - **Cross-border bank-statement verification Agent**: LangGraph routes uploaded PDF and CSV inputs by bank type, invokes country/bank-specific parsers, normalizes transaction fields, and checks totals against CSV. The typical per-statement handling time changed from roughly 15-20 minutes of manual work to 1-2 minutes.
   - **Yishangbao merchant-registration Agent**: a dialogue-led merchant onboarding flow that collects registration, bank, ID, business-license, and shareholder details; synchronizes with forms; and uses OCR plus Qwen multimodal extraction and cross-checking. The reported outcomes are approximately 70% less human intervention and 75% less manual entry.
   - **Derm AI online consultation**: a self-led project that combines a dermatology RAG knowledge base, multi-turn consultation, and FastAPI streaming responses.
4. Concise experience and education timeline using only verified resume content.
5. The public site uses a login entry, not a public chat prompt. Logged-in users reach chat on a separate route.

## Accounts, Verification, and API Keys

- Retain account-password registration and JWT authentication.
- Registration requires a six-digit email verification code before sign-in or chat access.
- QQ SMTP is used in production through private environment variables. The application uses an SMTP authorization code, never the QQ password.
- Verification codes are short-lived (10 minutes), one-time use, and subject to resend cooldown and IP/email rate limits. Responses should not leak whether an account already exists.
- A verified user can add, replace, or delete their own DeepSeek API key.
- The server encrypts the key before persistence with a deployment-provided encryption secret. API responses and UI show only a masked suffix. The full key is never logged, returned, or exposed to browser code.
- Chat requests use only the authenticated caller's decrypted key. A user without a key receives a clear setup prompt and cannot start a chat.

## Data and Deployment

- Preserve existing user and conversation records.
- Add version-controlled, reviewable database migrations for email-verification state and encrypted user-key metadata; do not use destructive schema operations.
- Use Supabase PostgreSQL, Upstash Redis, QQ SMTP, a Python-capable backend host, and Sites for the React frontend.
- Store database URLs, Redis URL, JWT secret, key-encryption secret, SMTP configuration, and other secrets only in hosted private environment variables. Commit only placeholders in `.env.example`.
- Add CORS and frontend API-base configuration needed for separate public frontend and backend origins.

## Removed Scope

- Learning-material UI and service code.
- Interview-review routes, schemas, models, services, tests, queueing, and workers.
- WebSocket and realtime-event routes, publishers, auth, and tests.
- Any frontend navigation and type definitions supporting those removed features.

## Validation

- Test registration, verification, duplicate/expired/invalid-code handling, resend cooldown, and throttling.
- Test that unverified accounts cannot log in or chat.
- Test encrypted key persistence, masking, replacement, deletion, and non-disclosure in API responses.
- Test that authenticated HTTP chat works with the caller's configured key and fails safely without one.
- Test that no public page contains the resume's phone, email, or portrait data.
- Run backend tests and frontend production build before deployment.
