# Progress Tracker

Update after every meaningful implementation change.

## Current Phase
- Phase 1 — Foundations (Unit 01 done)

## Current Goal
- Unit 02 — Database foundation

## Completed
- Unit 01 — Project scaffold (2026-10-05)
  - Deviations: Vite 8 template ships oxlint, replaced with ESLint flat config per spec; `baseUrl` omitted from tsconfig.app.json (deprecated in TS 6, `paths` works without it); Node 22 required (jsdom 30 fails on Node 20); backend dev port is 8001 (not 8000) because 8000 is used by another local Docker project — Makefile, vite proxy, README, CLAUDE.md, architecture.md and specs updated.

## In Progress
- None.

## Next Up
- Unit 02 — Database foundation
- Unit 03 — Google OAuth login & sessions

## Open Questions
- Exact OpenAI model ids for `LLM_MAIN_MODEL` / `LLM_FAST_MODEL` — proposed default: `.env.example` ships `openai:gpt-4.1` and `openai:gpt-4.1-mini`; the user confirms current best ids before Unit 07 manual testing (config only, no code change).
- Should automated senders (noreply, mailing lists with `List-Unsubscribe`) count as contacts? — proposed default: stored with `is_automated=true`, hidden by default in the Contacts page and excluded from `lookup_contact`; "Show automated" toggle reveals them.
- Contacts backfill window — proposed default: last 12 months, capped at 5,000 messages per direction (sent / received).
- Digest when nothing matches — proposed default: still send a short "Nothing matched your focus in the last N hours" email and record the run as `success` with `email_count = 0`.
- Multi-user / SaaS path: `gmail.modify` and `gmail.send` are Google restricted/sensitive scopes requiring OAuth verification + security assessment before public launch — proposed default: out of scope for v1; revisit before any public release.

## Architecture Decisions
- Python FastAPI backend + Vite React SPA — why: user preference for Python; no SSR needed for a local tool (planning interview, 2026-10-03).
- SQLAlchemy 2.0 async + Alembic instead of Drizzle — why: Drizzle is TypeScript-only; this is the standard Python equivalent (2026-10-03).
- LangGraph + LangChain `init_chat_model` + LangSmith — why: user wants complex agentic loops later; `interrupt()` gives native human-in-the-loop approvals; provider-agnostic models with OpenAI first (2026-10-03).
- Live Gmail API access, no local mailbox mirror — why: always fresh, no sync engine; contacts are the only derived data and use a metadata-only sync (2026-10-03).
- Draft-then-approve for every mailbox mutation, implemented as LangGraph interrupts rendered as inline approval cards — why: user wants control; the only exception is digest emails to the user's own address, guarded in code (2026-10-03).
- Google OAuth doubles as app login; server-side sessions with hashed tokens; Fernet-encrypted OAuth tokens — why: one sign-in step, extends to multi-user (2026-10-03).
- `users` table + `user_id` scoping + `EmailProvider` interface from day one — why: v1 is single-user/Gmail-only but SaaS and other providers are the stated direction (2026-10-03).
- Scheduled digests are user-defined (days, time, timezone, focus, filters) and delivered by email to self; run by an APScheduler worker process with scheduler-agnostic job functions — why: no Redis in v1, clean seam for Celery + Redis later (2026-10-03).
- Triage both on demand (chat tool) and scheduled (digests) — why: user requirement (2026-10-03).
- Compose new emails is in v1 alongside replies — why: user requirement (2026-10-03).
- Contacts list = everyone the user emailed or received email from, plus manually added contacts; derived via Gmail header metadata sync (12-month backfill, 30-min incremental) — why: user requirement; enables name→address resolution for compose (2026-10-03).
- Dark-only, technical/dense UI with emerald accent; sidebar + chat layout; cards inline in chat — why: user choice (2026-10-03).
- Tests: pytest (real Postgres test DB + fakes), Vitest, one Playwright smoke; no network in tests — why: per-unit review loop needs fast deterministic tests (2026-10-03).
- Claude Code with branch per unit (`unit/NN-name`) and `feat(NN): <name>` commits (2026-10-03).

## Session Notes
- Blueprint generated 2026-10-03. Start with `context/specs/01-project-scaffold.md`.
- Units 10–19 are written slightly lighter on file-level detail; re-check each against the codebase before implementing.
