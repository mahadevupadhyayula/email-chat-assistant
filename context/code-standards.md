# Code Standards

## General
- Small, single-purpose modules. One domain per service module (`services/contacts.py`, `services/digests.py`, …).
- Fix root causes, not symptoms. No dead code, no commented-out code, no `print` debugging left behind.
- No new abstraction until there are two real callers — except the deliberate seams named in architecture.md (`EmailProvider`, LLM factory, scheduler-agnostic jobs).
- Configuration only through `app/config.py:Settings` (backend) and Vite env (`import.meta.env.VITE_*`, frontend). No `os.environ` reads elsewhere.

## Language & Types
### Python
- Python 3.12, `from __future__ import annotations` not needed (use 3.12 syntax: `list[str]`, `X | None`).
- mypy `strict = true`. No `Any` in function signatures except where a third-party API forces it — then wrap it and return typed data immediately. `# type: ignore` requires an error code and a reason comment.
- Pydantic v2 models for every API request/response (`app/schemas/`). Provider-neutral mail types are `@dataclass(frozen=True, slots=True)` in `app/email/types.py`.
- Async everywhere on the request path (`async def`, `AsyncSession`). The Gmail SDK is sync — call it through `anyio.to_thread.run_sync` inside `GmailProvider` only.

### TypeScript
- `strict: true`, `noUncheckedIndexedAccess: true`. No `any`; use `unknown` + narrowing.
- API types come from the generated `src/lib/api/schema.d.ts` (`pnpm gen:api`). Do not hand-write types that mirror backend schemas. SSE event payloads are typed in `src/lib/sse-events.ts` and mirrored from `backend/app/schemas/stream.py`.
- Form validation with zod schemas colocated with the form.

## FastAPI Conventions
- App factory `create_app(settings: Settings | None = None) -> FastAPI` in `app/main.py`. Routers are `APIRouter(prefix="/api/<domain>", tags=["<domain>"])`.
- Endpoint body: validate → call one service function → return a schema. No business logic in routers.
- Dependencies in `app/api/deps.py`: `get_db` (yields `AsyncSession`, commits on success, rolls back on exception), `get_current_user`, `get_email_provider`, `get_graph`, `get_settings`.
- Every response model declared via `response_model=` so OpenAPI is complete for type generation.

## LangGraph / LangChain Conventions
- One graph, built by `build_graph(checkpointer) -> CompiledStateGraph` in `app/agent/graph.py`. Nodes: `agent` (model with tools bound) and `tools` (`ToolNode`), conditional edge via `tools_condition`.
- Tools are `@tool`-decorated `async def` functions in `app/agent/tools/<area>.py`, registered in `app/agent/tools/__init__.py:ALL_TOOLS`. Tool args are typed with Pydantic `args_schema`. Tools read `user_id`, `email_provider` and `session_factory` from `config["configurable"]` via `app/agent/context.py:get_tool_context(config)`.
- Tools return JSON-serialisable dicts with a `"ui"` key (`{"type": "email_list" | "thread" | "triage" | "send_receipt" | "action_receipt" | "none", ...}`; `none` = nothing to render) and a compact `"llm"` string the model sees. Use `response_format="content_and_artifact"`: content = the `llm` string, artifact = the `ui` dict.
- Mutation tools: build the preview payload → `decision = interrupt(payload)` → execute only if `decision["decision"] == "approve"` → log `mail_actions` → return receipt. Nothing with side effects before `interrupt()`.
- Prompts live in `app/agent/prompts.py` as module-level constants; include today's date and the user's email/timezone via a formatter function.
- Models only from `app/llm/factory.py`: `get_main_model()` (agent), `get_fast_model()` (triage classification, digest summaries).

## Naming
| Thing | Convention | Example |
| ----- | ---------- | ------- |
| Python modules | snake_case | `contact_sync.py` |
| Python classes | PascalCase | `GmailProvider`, `DigestSchedule` |
| Python functions | snake_case verbs | `list_contacts`, `run_digest` |
| DB tables | plural snake_case | `digest_schedules` |
| API paths | `/api/<plural-noun>` kebab-free | `/api/contacts/{contact_id}` |
| React components | PascalCase file + export | `EmailCard.tsx` |
| Hooks | `useX` camelCase in `hooks.ts` or own file | `useContacts` |
| TS non-component files | kebab-case | `sse-events.ts` |
| CSS tokens | `--kebab-case` | `--accent-primary` |
| Tests (py) | `test_<module>.py`, `test_<behaviour>` | `test_rejects_other_recipient` |
| Tests (ts) | `<Component>.test.tsx` colocated | `EmailCard.test.tsx` |

## API / Server Logic
- Input validated by Pydantic schemas; strings trimmed; emails validated with `pydantic.EmailStr` and lowercased.
- Auth: `user: User = Depends(get_current_user)` on every protected endpoint.
- Error shape (all non-2xx): `{"error": {"code": "<snake_case_code>", "message": "<human readable>"}}`. Codes: `unauthenticated`, `not_found`, `validation_error`, `conflict`, `provider_reauth_required`, `provider_error`, `llm_error`, `internal_error`.
- Domain errors in `app/services/errors.py` (`NotFoundError`, `ConflictError`, `ProviderAuthError`, `ProviderError`, `SelfSendViolation`) mapped to HTTP by exception handlers registered in `create_app`.
- Lists return `{"items": [...], "next_cursor": str | null}` when paginated (contacts); otherwise `{"items": [...]}`.

## Error Handling & Logging
- Python: raise domain errors; never return `None` to signal failure. Catch third-party exceptions only at the boundary module (`email/gmail/`, `llm/`) and re-raise as domain errors.
- Logging via stdlib `logging` configured in `app/main.py` (`LOG_LEVEL` env). Log event + ids; never log email bodies, tokens, or full addresses lists at INFO (DEBUG only for addresses).
- Streaming errors are emitted as an SSE `error` event `{code, message}` followed by `done`; the stream never ends silently.
- Frontend: query/mutation errors render inline next to the failed element; `provider_reauth_required` anywhere sets the global reconnect banner (via a QueryClient `onError` hook); toasts (`sonner`) only for successful background actions ("Contact added").

## Styling
- Tailwind utilities mapped to the CSS tokens in `ui-context.md` (`bg-surface`, `text-fg-muted`, `border-line`, `bg-brand`). **No raw hex/rgb values** in components; no arbitrary colour values (`bg-[#...]`).
- Radius: `rounded-sm` (4px) for inputs/badges, `rounded-md` (6px) for buttons/cards, `rounded-lg` (8px) for dialogs.
- Compose variants with `cn()` from `src/lib/utils.ts`; use `cva` for components with >2 variants.

## Testing
- **Backend unit tests:** pytest + pytest-asyncio (`asyncio_mode = "auto"`) in `backend/tests/unit/` — pure logic (parsers, guards, cron building, stream mapping, prompts).
- **Backend integration tests:** `backend/tests/integration/` — FastAPI app via `httpx.AsyncClient(transport=ASGITransport(app))` against the real Postgres test DB (`TEST_DATABASE_URL`). Schema created by running Alembic `upgrade head` once per session; tables truncated between tests. Authenticated client fixture uses `POST /api/auth/dev-login`.
- **Fakes:** `app/email/fake.py:FakeEmailProvider` (in-memory messages/labels, records sends/archives) and `app/llm/fake.py:ScriptedChatModel` (returns a queued list of `AIMessage`s, supports `bind_tools`). Both are production code under `app/` so E2E mode can use them.
- **Frontend tests:** Vitest + Testing Library + jsdom, colocated `*.test.tsx`. Mock the network at `lib/api/client.ts` / `lib/sse.ts` level with `vi.mock`.
- **E2E:** Playwright smoke in `frontend/e2e/` against backend started with `APP_ENV=e2e` (fakes enabled, dev-login).
- **Every unit must:** add tests for all new logic, the happy path, at least one failure path, and an ownership test (other user's resource → 404) for every new user-owned endpoint.
- Commands: `make test` (both suites), `cd backend && uv run pytest`, `cd frontend && pnpm test`, `make e2e`.

## File Organization
- `backend/app/api/` — routers only. `backend/app/schemas/` — Pydantic API models. `backend/app/services/` — logic + DB. `backend/app/db/models/` — SQLAlchemy models. `backend/app/email/` — provider layer. `backend/app/llm/` — model factory + fakes. `backend/app/agent/` — graph, tools, prompts, streaming. `backend/app/worker/` — scheduler process + jobs.
- `frontend/src/features/<feature>/` — pages, feature components, `hooks.ts` (TanStack Query hooks), `api.ts` (typed calls via client). `frontend/src/components/layout/` — app chrome. `frontend/src/components/ui/` — shadcn primitives.
