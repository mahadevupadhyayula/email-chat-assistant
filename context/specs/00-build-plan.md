# Build Plan — Email Assistant Chat

When every unit is complete, a signed-in user can chat with an assistant that searches, triages, replies to, composes and organises their Gmail behind approval cards, manage a contacts list derived from their mail, and receive user-defined scheduled digests by email.

## How to use this plan
Build units strictly in order. Each unit has a spec file in this folder. Finish, test and review each unit before starting the next. Per-unit loop: see `context/ai-workflow-rules.md`.

## Phases
| Phase | Units | Outcome |
| ----- | ----- | ------- |
| Foundation | 01–04 | Both apps run, DB + migrations, Google login, dark app shell behind auth |
| Core chat | 05–09 | Gmail provider layer, persistent conversations, streaming LangGraph agent, wired chat UI, search/read tools with email cards |
| Contacts & sending | 10–13 | Contacts sync + page, reply/compose behind interrupt approvals, approval card UI |
| Triage & organise | 14–15 | On-demand triage card; archive/label with approval |
| Scheduled digests | 16–18 | Digest CRUD API + UI, APScheduler worker sending digests to self, periodic contact sync |
| Hardening | 19 | Playwright core-flow smoke, empty/error state pass |

## Units
| # | Unit | Builds | Boundary | Depends on | Spec |
| - | ---- | ------ | -------- | ---------- | ---- |
| 01 | Project scaffold | Repo layout, backend + frontend init, Docker Postgres, tooling, smoke tests, `/api/health` | Tooling | — | [01-project-scaffold.md](01-project-scaffold.md) |
| 02 | Database foundation | SQLAlchemy async setup, Alembic, `users`/`sessions`/`oauth_credentials`, test DB fixtures, health checks DB | Data | 01 | [02-database-foundation.md](02-database-foundation.md) |
| 03 | Google OAuth login & sessions | Login/callback/logout/me endpoints, encrypted tokens, session cookie, dev-login for tests | API/Auth | 02 | [03-google-oauth-login.md](03-google-oauth-login.md) |
| 04 | Frontend shell & auth guard | Tokens, fonts, shadcn, Login page, RequireAuth, AppShell + Sidebar with placeholder data, typed API client | UI | 03 | [04-frontend-shell.md](04-frontend-shell.md) |
| 05 | Email provider layer | `EmailProvider` protocol, `GmailProvider` (search, get_thread), `FakeEmailProvider`, reauth handling, diagnostic `/api/mail/*` endpoints | Integration | 03 | [05-email-provider-layer.md](05-email-provider-layer.md) |
| 06 | Conversations API | `conversations` table + CRUD endpoints with ownership | API/Data | 03 | [06-conversations-api.md](06-conversations-api.md) |
| 07 | Agent core & streaming | LLM factory + scripted fake, LangGraph graph with Postgres checkpointer, SSE send-message endpoint, transcript endpoint, LangSmith | Agent/API | 05, 06 | [07-agent-core-streaming.md](07-agent-core-streaming.md) |
| 08 | Chat UI wired | Real sidebar conversations, ChatPage streaming, Markdown, suggested prompts, stop, error/retry, reconnect banner | UI | 04, 07 | [08-chat-ui.md](08-chat-ui.md) |
| 09 | Search & read tools | `search_emails`, `get_thread` tools; tool status rows; EmailCard + ThreadCard rendering | Agent + UI | 08 | [09-search-read-tools.md](09-search-read-tools.md) |
| 10 | Contacts sync backend | `contacts` + `contact_sync_state`, metadata sync service, backfill after login, list + sync endpoints | Data/Integration | 05 | [10-contacts-sync.md](10-contacts-sync.md) |
| 11 | Contacts page & manual contacts | Add/rename/delete endpoints, Contacts page with search, automated toggle, Sync now | UI + API | 04, 10 | [11-contacts-page.md](11-contacts-page.md) |
| 12 | Reply & compose with approval (backend) | `lookup_contact`, `send_reply`, `compose_email` tools with `interrupt()`, resume endpoint, `mail_actions`, provider send | Agent/API | 09, 10 | [12-send-approval-backend.md](12-send-approval-backend.md) |
| 13 | Approval card UI | Editable send approval card, approve/reject → resume stream, receipts, restore pending approval | UI | 08, 12 | [13-approval-card-ui.md](13-approval-card-ui.md) |
| 14 | On-demand triage | `triage_inbox` tool using fast model, TriageCard | Agent + UI | 09 | [14-triage.md](14-triage.md) |
| 15 | Organise with approval | `archive_emails`, `label_emails` tools with interrupt, list approval card with per-row opt-out | Agent + UI | 13 | [15-organise-approval.md](15-organise-approval.md) |
| 16 | Digest schedules API | `digest_schedules` + `digest_runs` tables, CRUD + validation, schedule summary | API/Data | 03 | [16-digest-schedules-api.md](16-digest-schedules-api.md) |
| 17 | Digests UI | Digest list, create/edit form, enable toggle, delete | UI | 04, 16 | [17-digests-ui.md](17-digests-ui.md) |
| 18 | Digest worker | APScheduler worker process, `run_digest` job, self-send guard, periodic contacts sync, Send now + run history | Background | 10, 16, 17 | [18-digest-worker.md](18-digest-worker.md) |
| 19 | E2E smoke & state polish | Playwright core flow against fakes, empty/error state audit | Testing/UI | 01–18 | [19-e2e-polish.md](19-e2e-polish.md) |

## Dependency introduction
| Package | Introduced in unit | Why |
| ------- | ------------------ | --- |
| `fastapi`, `uvicorn[standard]`, `pydantic-settings` | 01 | API server + config |
| `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy` (dev) | 01 | Tests, lint, types |
| Vite React TS template, `tailwindcss`, `@tailwindcss/vite`, `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `prettier`, `eslint` | 01 | Frontend base + tests |
| `sqlalchemy[asyncio]`, `asyncpg`, `alembic` | 02 | DB + migrations |
| `google-auth`, `google-auth-oauthlib`, `cryptography`, `itsdangerous` | 03 | OAuth, token encryption, signed state cookie |
| `react-router`, `@tanstack/react-query`, `lucide-react`, `@fontsource-variable/inter`, `@fontsource/jetbrains-mono`, shadcn (+ `class-variance-authority`, `clsx`, `tailwind-merge`, Radix deps), `openapi-typescript` (dev) | 04 | Routing, server state, UI kit, typed API |
| `google-api-python-client`, `html2text` | 05 | Gmail API, HTML→text bodies |
| `langgraph`, `langchain`, `langchain-core`, `langchain-openai`, `langgraph-checkpoint-postgres`, `psycopg[binary,pool]`, `sse-starlette` | 07 | Agent, models, checkpointer, SSE |
| `react-markdown`, `remark-gfm` | 08 | Assistant Markdown |
| `sonner` (via shadcn), `react-hook-form`, `zod`, `@hookform/resolvers` | 11 | Toasts, contact form |
| `tzdata` | 16 | IANA timezone validation on all platforms |
| `apscheduler>=3.10,<4` | 18 | Worker scheduling |
| `@playwright/test` | 19 | E2E smoke |

## Notes
- **Risk — Gmail OAuth setup:** Unit 03 manual verification requires a Google Cloud project with the Gmail API enabled, an OAuth client (Web), redirect URI `http://localhost:8001/api/auth/google/callback`, consent screen in Testing mode with the user's address as a test user. README (Unit 03) documents the steps.
- **Risk — LangGraph interrupts inside tools:** tools re-execute from the top on resume; Unit 12 tests assert no side effects happen before `interrupt()`.
- **Sequencing:** contacts (10–11) come before compose (12) so `lookup_contact` has data. Digest API/UI (16–17) do not depend on the agent and could be built after Unit 04 if the user wants to parallelise, but keep the numbered order by default.
- **Re-check before implementing:** specs 10–19 are lighter on file-level detail; re-read the current code (especially `agent/streaming.py`, `features/chat/`, and `email/types.py`) before starting each, since earlier units may have shifted names.
