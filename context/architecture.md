# Architecture

## Stack
| Layer | Technology | Role | Why |
| ----- | ---------- | ---- | --- |
| Backend language | Python 3.12 | API, agent, worker | User preference; best ecosystem for LangGraph |
| Package/env manager | uv | Dependency + venv management, script runner | Fast, lockfile, single tool |
| API framework | FastAPI + Uvicorn | HTTP API, SSE streaming | Async, Pydantic validation, OpenAPI for typed frontend client |
| Validation / settings | Pydantic v2, pydantic-settings | Request/response schemas, env config | Native to FastAPI |
| Database | PostgreSQL 16 (Docker Compose) | All persistent data incl. LangGraph checkpoints | Multi-user ready; required by LangGraph Postgres checkpointer |
| ORM / migrations | SQLAlchemy 2.0 (async, asyncpg) + Alembic | App tables + schema migrations | Standard Python ORM; Drizzle is TS-only |
| Agent runtime | LangGraph (`StateGraph`, `ToolNode`, `interrupt()`, `AsyncPostgresSaver`) | Agent loop, tool calling, human-in-the-loop approvals, conversation state | Built for complex agentic loops later; interrupts = approval cards |
| LLM abstraction | LangChain `init_chat_model` behind `app/llm/factory.py` | Provider-agnostic chat models; OpenAI first | Swap providers by env var |
| LLM provider (v1) | OpenAI via `langchain-openai` | Main model (agent) + fast model (triage, digests) | User choice |
| Tracing | LangSmith (env-enabled) | Trace every agent run | Debugging agent loops |
| Mail | Gmail API via `google-api-python-client` behind `EmailProvider` | Search, read, send, label, archive, contacts sync | Gmail v1; interface for future providers |
| Auth | Google OAuth 2.0 (`google-auth-oauthlib`) + server-side sessions | Login + Gmail authorisation in one consent | Single sign-in step; extends to multi-user |
| Secrets at rest | `cryptography` Fernet | Encrypt OAuth tokens in DB | Tokens must never be readable from a DB dump |
| Scheduler | APScheduler 3.x in a separate worker process | Digest cron jobs, periodic contacts sync | No Redis in v1; job functions are scheduler-agnostic for a later Celery move |
| Frontend | Vite + React 19 + TypeScript (strict) | SPA | No SSR needed for a local tool |
| Frontend pkg manager | pnpm | | Fast, strict |
| Routing / data | React Router 7 (library mode), TanStack Query 5 | Pages; server state + cache | Standard, minimal |
| UI | Tailwind CSS v4, shadcn/ui, lucide-react | Components, styling, icons | Owned components, token-driven |
| API types | `openapi-typescript` | Generates TS types from FastAPI's `/openapi.json` | Single source of truth for API shapes |
| Forms | react-hook-form + zod | Digest + contact forms | Typed validation |
| Tests | pytest + pytest-asyncio + httpx; Vitest + Testing Library; Playwright | Backend, frontend, E2E smoke | See code-standards.md |
| Lint/format/types | Ruff, mypy (strict); ESLint + Prettier, `tsc --noEmit` | | |

## Folder Structure
```
email-assistant-chat/
├── CLAUDE.md
├── README.md
├── Makefile                      # install/dev/test/lint/build/e2e/worker/migrate targets
├── docker-compose.yml            # postgres:16 — creates email_assistant + email_assistant_test DBs
├── docker/postgres-init.sql      # creates the test database
├── .env.example                  # all env vars, documented
├── context/                      # planning docs + specs (this folder)
├── backend/
│   ├── pyproject.toml            # uv project, ruff, mypy, pytest config
│   ├── alembic.ini
│   ├── alembic/                  # env.py + versions/
│   ├── app/
│   │   ├── main.py               # create_app(): FastAPI factory, router registration, lifespan
│   │   ├── config.py             # Settings (pydantic-settings); get_settings()
│   │   ├── api/                  # HTTP routers only (thin): health, auth, conversations, chat, mail, contacts, digests
│   │   │   └── deps.py           # FastAPI dependencies: get_db, get_current_user, get_email_provider, get_graph
│   │   ├── schemas/              # Pydantic request/response models (API contract)
│   │   ├── services/             # Business logic + DB access; one module per domain
│   │   ├── db/
│   │   │   ├── base.py           # DeclarativeBase, naming conventions, mixins
│   │   │   ├── session.py        # async engine + session factory
│   │   │   └── models/           # one module per table group
│   │   ├── security/             # crypto.py (Fernet), sessions.py (token gen/hash), oauth.py (Google flow helpers)
│   │   ├── email/                # EmailProvider protocol, types, gmail/ implementation, fake.py
│   │   ├── llm/                  # factory.py (get_main_model/get_fast_model), fake.py (scripted test model)
│   │   ├── agent/                # graph.py, state.py, prompts.py, checkpointer.py, streaming.py, tools/
│   │   └── worker/               # main.py (APScheduler process), jobs/ (scheduler-agnostic async jobs)
│   └── tests/
│       ├── conftest.py           # app/client/db fixtures, fake provider + fake LLM wiring
│       ├── unit/
│       └── integration/
└── frontend/
    ├── package.json
    ├── vite.config.ts            # /api proxy → http://localhost:8000
    ├── components.json           # shadcn config
    ├── e2e/                      # Playwright specs (Unit 19)
    └── src/
        ├── main.tsx              # QueryClient + Router providers
        ├── App.tsx               # route table
        ├── styles/globals.css    # tokens (ui-context.md) + Tailwind
        ├── components/ui/        # shadcn-generated (protected)
        ├── components/layout/    # AppShell, Sidebar, ReconnectBanner
        ├── features/
        │   ├── auth/             # LoginPage, RequireAuth, useMe
        │   ├── chat/             # ChatPage, MessageList, Composer, cards/, useChatStream
        │   ├── contacts/         # ContactsPage, ContactForm, hooks
        │   └── digests/          # DigestsPage, DigestForm, RunHistory, hooks
        └── lib/
            ├── api/              # client.ts (fetch wrapper), schema.d.ts (generated), errors.ts
            ├── sse.ts            # POST-capable SSE parser
            └── utils.ts          # cn() class merging helper
```

## System Boundaries
- `backend/app/api/` — parses/validates HTTP input, resolves dependencies, calls one service function, maps results/errors to HTTP. **Never** imports SQLAlchemy models' query API, the Gmail SDK, or LangChain models directly.
- `backend/app/services/` — all business logic and all DB reads/writes. Every function takes `user_id` (or a `User`) and scopes queries by it. Never imports `fastapi`; services raise domain errors from `app/services/errors.py`, which routers map to HTTP responses (exception: `fastapi.BackgroundTasks` is passed in from routers, never imported for anything else).
- `backend/app/email/` — the only place that talks to Gmail (`googleapiclient`). Exposes the `EmailProvider` protocol and provider-neutral dataclasses. No DB access except via a `CredentialStore` callback for refreshed tokens.
- `backend/app/llm/` — the only place that constructs chat models. Nothing else imports `langchain_openai` or any provider package.
- `backend/app/agent/` — graph definition, state, prompts, tools. Tools get their `EmailProvider`, `user_id` and DB session factory from the LangGraph `RunnableConfig["configurable"]`, never from globals. Tools never import `googleapiclient`.
- `backend/app/worker/` — process entrypoint and scheduling. `worker/jobs/*.py` contain plain `async def` job functions with **no** APScheduler imports (Celery seam). Only `worker/main.py` imports APScheduler.
- `backend/app/security/` — crypto and OAuth helpers; the only module that sees decrypted tokens is `services/credentials.py` via `security/crypto.py`.
- `frontend/src/features/*` — feature UI + hooks. Talks to the backend only through `src/lib/api/client.ts` and `src/lib/sse.ts`. No `fetch` calls elsewhere.
- `frontend/src/components/ui/` — generated shadcn primitives; feature code wraps them, does not edit them.

## Data Flow
**Regular request:** React component → TanStack Query hook (`features/*/hooks.ts`) → `lib/api/client.ts` (`fetch('/api/...', {credentials: 'include'})`) → Vite proxy → FastAPI router (`api/*.py`) → `deps.get_current_user` (session cookie → `sessions` table) → `services/*` (SQLAlchemy async session) → Postgres → Pydantic response schema → JSON.

**Chat turn:** `useChatStream` POSTs `/api/conversations/{id}/messages` `{content}` → `api/chat.py` → `services/chat.py:stream_turn()` builds `config = {"configurable": {"thread_id": conversation_id, "user_id", "email_provider", "session_factory"}}` → `graph.astream(..., stream_mode=["messages", "updates"])` → `agent/streaming.py` maps LangGraph chunks to SSE events (`token`, `tool_start`, `tool_result`, `approval_required`, `error`, `done`) → frontend appends to the message list. State is checkpointed in Postgres by `AsyncPostgresSaver` under `thread_id = conversation.id`.

**Approval:** a mutation tool calls `interrupt(payload)` → stream emits `approval_required` and ends → card renders → user clicks Approve/Reject/edits → POST `/api/conversations/{id}/resume` `{decision, edits}` → `graph.astream(Command(resume=...))` → tool re-runs, receives the decision from `interrupt()`, executes or skips the mutation, writes a `mail_actions` row → stream continues.

**Scheduled digest:** worker process → APScheduler `CronTrigger` per enabled `digest_schedules` row (reconciled from DB every 60 s) → `worker/jobs/digest.py:run_digest(schedule_id)` → `services/digests.py` builds Gmail query → `EmailProvider.search` → fast model summarises against focus instructions → `services/digests.py:send_digest_to_self()` (self-recipient guard) → `EmailProvider.send_message` → `digest_runs` row.

## Data Model
All ids are UUID v4 (`uuid` PK, server-generated in Python). All timestamps are `timestamptz` in UTC.

| Entity | Key fields | Relations | Owner |
| ------ | ---------- | --------- | ----- |
| `users` | id, email (unique, lowercase), name, avatar_url, created_at, updated_at | 1–N everything below | self |
| `sessions` | id, user_id, token_hash (sha256 hex, unique), expires_at, created_at | N–1 users | user |
| `oauth_credentials` | id, user_id, provider (`google`), encrypted_refresh_token, encrypted_access_token, access_token_expires_at, scopes (text[]), status (`active`\|`revoked`), created_at, updated_at; unique(user_id, provider) | N–1 users | user |
| `conversations` | id (= LangGraph thread_id), user_id, title (≤120 chars, default "New chat"), created_at, updated_at (bumped every turn) | N–1 users; 1–1 LangGraph thread | user |
| LangGraph checkpoint tables | managed by `AsyncPostgresSaver.setup()` (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`) | keyed by thread_id | via conversation |
| `mail_actions` | id, user_id, conversation_id (nullable), action (`send`\|`archive`\|`label`), status (`executed`\|`rejected`\|`failed`), target_message_ids (text[]), recipients (text[]), subject, error, created_at | N–1 users, N–1 conversations | user |
| `contacts` | id, user_id, email (lowercase), display_name, source (`auto`\|`manual`), sent_count, received_count, last_interaction_at, is_automated, created_at, updated_at; unique(user_id, email) | N–1 users | user |
| `contact_sync_state` | user_id (PK), status (`idle`\|`running`\|`failed`), watermark (timestamptz — last synced up to), last_error, updated_at | 1–1 users | user |
| `digest_schedules` | id, user_id, name (≤80), days_of_week (smallint[] 0=Mon..6=Sun), time_of_day (time), timezone (IANA string), focus_instructions (text ≤2000), filter_senders (text[]), filter_labels (text[]), filter_keywords (text[]), lookback_hours (int 1–168, default 24), enabled (bool), created_at, updated_at | N–1 users; 1–N digest_runs | user |
| `digest_runs` | id, schedule_id, user_id, trigger (`schedule`\|`manual`), status (`running`\|`success`\|`failed`), email_count, sent_message_id, error, started_at, finished_at | N–1 digest_schedules | user |

Deletes are hard deletes. Deleting a conversation also deletes its LangGraph thread (`checkpointer.adelete_thread`). Deleting a digest schedule cascades its runs.

## Storage Model
- **Database (Postgres):** all tables above, including LangGraph checkpoints (the source of truth for chat transcripts and pending interrupts).
- **File/blob storage:** none in v1. Email bodies are never stored in app tables — they're fetched live from Gmail and only exist inside checkpointed tool messages (truncated).
- **Cache:** none in v1 beyond Google client token refresh in memory per request.
- **Client state:** TanStack Query cache; in-flight streaming message buffer and approval-card edit state in React state. Nothing in localStorage except the sidebar collapsed flag.

## Auth and Access Model
- **Authentication:** Google OAuth 2.0 authorization-code flow (`access_type=offline`, `prompt=consent`, state parameter in a short-lived signed cookie). Scopes: `openid`, `email`, `profile`, `https://www.googleapis.com/auth/gmail.modify`, `https://www.googleapis.com/auth/gmail.send`. On callback: upsert `users`, upsert encrypted `oauth_credentials`, create a `sessions` row, set cookie `ea_session` (random 32-byte token, httpOnly, SameSite=Lax, Secure=false on localhost, 30-day expiry). Only the SHA-256 hash is stored.
- **Unauthenticated users can:** see the Login page, call `GET /api/health`, `GET /api/auth/google/login`, `GET /api/auth/google/callback`. Everything else returns 401 `{code: "unauthenticated"}`.
- **Ownership:** every row belongs to exactly one user via `user_id`. No sharing, no roles in v1.
- **Enforcement:** `deps.get_current_user` on every protected router; every service function filters by `user_id`; fetching another user's resource returns 404 (not 403).
- **Test login:** `POST /api/auth/dev-login` exists **only** when `APP_ENV` is `test` or `e2e` (router not registered otherwise).

## Integrations & Background Work
- **Gmail API:** via `GmailProvider(credentials)`. Access tokens refreshed by `google-auth`; refreshed tokens persisted through `services/credentials.py`. A `RefreshError` / 401 marks credentials `revoked` and raises `ProviderAuthError` → API error code `provider_reauth_required` (HTTP 401) / SSE `error` event with the same code.
- **LLM:** `app/llm/factory.py` reads `LLM_MAIN_MODEL` and `LLM_FAST_MODEL` (format `provider:model`, passed to `init_chat_model`). `fake:scripted` returns the test `ScriptedChatModel`. API keys come from env (`OPENAI_API_KEY`), never from the client. Timeouts: 60 s per model call, 2 retries.
- **LangSmith:** enabled when `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` set; project `LANGSMITH_PROJECT=email-assistant-chat`. Disabled in tests.
- **Streaming:** SSE over POST using `sse-starlette`'s `EventSourceResponse`.
- **Background tasks:** initial contacts backfill runs via FastAPI `BackgroundTasks` after OAuth callback and on "Sync now". Scheduled work (digests, 30-minute contact sync) runs in the worker process (`make worker`).
- **Secrets:** `.env` (git-ignored): `DATABASE_URL`, `TEST_DATABASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `TOKEN_ENCRYPTION_KEY` (Fernet), `SESSION_SECRET` (state-cookie signing), `OPENAI_API_KEY`, `LLM_MAIN_MODEL`, `LLM_FAST_MODEL`, `LANGSMITH_*`, `APP_ENV`, `FRONTEND_URL`.

## Invariants
1. Routers in `backend/app/api/` never execute SQL, never import `googleapiclient`, and never construct LLMs — they call exactly one `services/*` function per endpoint.
2. Every service query on a user-owned table filters by `user_id`; a resource owned by another user is reported as not found (404).
3. Every mailbox mutation (`send_message`, `archive`, `apply_label`, `create_label`) called from the agent happens only after `interrupt()` returns a decision of `approve`; every executed, rejected or failed mutation writes a `mail_actions` row. No code with side effects runs before the `interrupt()` call inside a tool (tools re-execute on resume).
4. The only send path that skips approval is `services/digests.py:send_digest_to_self()`, which calls `assert_self_recipient()` and raises `SelfSendViolation` unless To is exactly `[user.email]` with no Cc/Bcc.
5. Only `backend/app/email/gmail/` imports `googleapiclient`; only `backend/app/llm/` imports provider packages (`langchain_openai`, `openai`, and any future `langchain_<provider>`). Agent, services and worker use `EmailProvider` and `get_main_model()/get_fast_model()`.
6. OAuth tokens are stored only Fernet-encrypted, are never logged, never returned by any API response, and never sent to the frontend or to the LLM.
7. Tests never make network calls: `FakeEmailProvider` and `ScriptedChatModel` are used in all backend tests and in the E2E run; `LANGSMITH_TRACING` is forced false in tests.
8. `worker/jobs/*.py` never import APScheduler; only `worker/main.py` does.
9. The frontend never calls `fetch` outside `src/lib/api/client.ts` and `src/lib/sse.ts`, and never stores tokens; auth is the httpOnly cookie only.
10. Email body text passed to the LLM is truncated to 8,000 characters per message and 30,000 characters per tool result.
