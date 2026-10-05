# Email Assistant Chat

A local, chat-based assistant that searches, triages, drafts, composes and organises your Gmail — acting on the mailbox only after you approve — and emails you scheduled digests built from focus topics you define.

## Application Building Context

Read these files in order before implementing anything or making any architectural decision:

1. `context/project-overview.md` — product definition, goals, features, scope
2. `context/architecture.md` — stack, system boundaries, storage, auth, invariants
3. `context/ui-context.md` — theme, colour tokens, typography, components, layout
4. `context/code-standards.md` — implementation rules and conventions
5. `context/ai-workflow-rules.md` — scoping rules, workflow, definition of done
6. `context/progress-tracker.md` — current phase, completed work, open questions, next unit

Feature specs live in `context/specs/`. The build order is `context/specs/00-build-plan.md`.

## Rules

- Implement one spec at a time, exactly as written. Do not build beyond the current spec's scope.
- Update `context/progress-tracker.md` after each meaningful change.
- If implementation changes architecture, scope or standards, update the relevant context file before continuing.
- If a requirement is missing or ambiguous, stop and add it to Open Questions in `progress-tracker.md` instead of guessing.
- Never execute a mailbox mutation (send, archive, label) without a LangGraph `interrupt()` approval — see Invariants in `context/architecture.md`.

## Commands

(Exist after Unit 01. Run from the repo root.)

- Start Postgres: `docker compose up -d db`
- Install: `make install` (runs `uv sync` in `backend/` and `pnpm install` in `frontend/`)
- Dev backend: `make dev-backend` (uvicorn on :8000, reload)
- Dev frontend: `make dev-frontend` (Vite on :5173, proxies `/api` → :8000)
- Worker: `make worker` (from Unit 18)
- Migrations: `make migrate` (`uv run alembic upgrade head`, from Unit 02)
- Test: `make test` (backend pytest + frontend Vitest)
- E2E: `make e2e` (Playwright, from Unit 19)
- Lint / typecheck: `make lint` (ruff check, ruff format --check, mypy, eslint, tsc --noEmit)
- Build: `make build` (frontend production build)
