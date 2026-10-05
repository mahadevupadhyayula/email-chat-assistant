# Unit 19: E2E smoke & state polish

## What to build
A Playwright smoke suite covering the core flow against a backend in `APP_ENV=e2e`: fake Gmail, a deterministic rule-based fake LLM, and dev-login. Plus an audit pass making every empty, loading and error state listed in project-overview.md and ui-context.md match the spec.

## Why
This is the final check that the full chat → tool → card → approval → send loop works end to end. It catches regressions in future work.

## Scope
**In scope**
- `app/llm/fake_rules.py` `RuleBasedChatModel` (`LLM_MAIN_MODEL=fake:rules` in e2e).
- E2E config: Playwright, backend + frontend web servers, seeded fake provider.
- Specs: auth redirect, search with cards, reply approval → sent receipt, contacts page, digest create.
- State audit fixes (only to match existing specs; no new features).

**Out of scope (do not build in this unit)**
- CI, visual regression, cross-browser runs (Chromium only), deployment.

## Prerequisites
- Units 01–18 complete.

## How to build it

### Backend e2e mode
- `RuleBasedChatModel(BaseChatModel)` — inspects the last message:
  - If it's a `ToolMessage` → returns a fixed summary text per tool name (`search_emails` → "Here's what I found.", `send_reply` → "Done — your reply was sent." or "Okay, I won't send it." based on content).
  - If the last human message contains "invoice" → tool call `search_emails{query:"invoice"}`; contains "reply to sam" → tool call `send_reply{thread_id: <Sam's seeded thread id>, body: "Yes, Thursday works."}`; otherwise → text "I can search, triage and draft emails."
  - Supports `bind_tools` (returns self) and streaming like `ScriptedChatModel`.
- Factory: `fake:rules` → `RuleBasedChatModel()`; `fast` stays `fake:scripted` with a default structured response.
- `e2e` env: fresh seeded `FakeEmailProvider` per process; dev-login enabled; contacts sync on dev-login runs synchronously against the fake so the Contacts page has data.

### Playwright
- `pnpm add -D @playwright/test && pnpm exec playwright install chromium`.
- `frontend/playwright.config.ts`: `testDir: "e2e"`, Chromium only, `baseURL: "http://localhost:5174"`, `webServer: [ { command: "cd ../backend && APP_ENV=e2e DATABASE_URL=$TEST_DATABASE_URL uv run alembic upgrade head && APP_ENV=e2e DATABASE_URL=$TEST_DATABASE_URL uv run uvicorn app.main:app --port 8001", url: "http://localhost:8001/api/health" }, { command: "VITE_API_TARGET=http://localhost:8001 pnpm dev --port 5174", url: "http://localhost:5174" } ]`, `reuseExistingServer: false`.
- `vite.config.ts`: proxy target reads `process.env.VITE_API_TARGET ?? "http://localhost:8000"`.
- `e2e/fixtures.ts`: `signedInPage` fixture → `page.request.post("/api/auth/dev-login")` (cookie stored in context), then `page.goto("/")`. Truncate DB tables before each test via a `POST /api/e2e/reset` endpoint registered only in `e2e` env (truncates app tables + checkpoints, reseeds the fake).
- Specs (`e2e/core-flow.spec.ts`):
  1. `redirects to login when signed out` → `/login` with "Sign in with Google".
  2. `search shows email cards` → send "find invoice emails" → tool row "searching mail" → card containing `billing@saas.com` → text "Here's what I found."
  3. `reply requires approval then sends` → "reply to sam saying yes" → card "Approve reply" with To `sam@client.io` → edit body → "Approve & send" → receipt "Sent to sam@client.io"; reload → receipt still shown, composer enabled.
  4. `reject does not send` → same prompt → Reject → "Not sent — rejected".
  5. `contacts page lists synced contacts` → `/contacts` shows `priya@acme.com`.
  6. `create digest` → `/digests/new` → fill fields → Save → card shows "Mon–Fri · 08:00".
- Makefile: `e2e: cd frontend && pnpm exec playwright test`.

### State audit
Walk through and fix anything missing vs. spec (record each fix in progress-tracker Session Notes):
- Chat: empty conversation prompts; transcript loading skeleton; 404 conversation; stream error row + Retry; 409 messages; reconnect banner.
- Contacts: never-synced, syncing, failed, empty, empty search.
- Digests: empty list, form validation, run failed display.
- Keyboard: Enter/Shift+Enter, `⌘K`, `Esc` stop, `⌘Enter` approve; visible focus rings on all interactive elements; icon buttons have `aria-label`.
- `grep` checks: no raw hex in `src/**/*.tsx`; no `fetch(` outside `src/lib/`; no `googleapiclient` import outside `backend/app/email/gmail/`; no `langchain_openai` outside `backend/app/llm/`. Add these as a `make check-invariants` target (shell greps that fail on matches).

## Patterns, frameworks & concepts
- **Use:** deterministic fakes for E2E (Invariant 7); one smoke flow per core capability, not exhaustive UI testing.
- **Use:** role-based Playwright locators (`getByRole`, `getByText`) — no CSS selectors.
- **Avoid:** real Gmail or OpenAI in E2E; sleeps (`waitForTimeout`) — use auto-waiting assertions.

## Design
No new design. Audit fixes must use existing tokens and patterns from ui-context.md.

## Dependencies
- `@playwright/test` — E2E runner.

## Success criteria
- [ ] `make e2e` passes all 6 specs locally from a clean DB, in under 2 minutes.
- [ ] `make check-invariants` passes.
- [ ] Every state in the audit list was checked and matches the spec (notes recorded).

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `backend/tests/unit/llm/test_fake_rules.py` | `test_rules_emit_expected_tool_calls` | "find invoice emails" → `search_emails` call; "reply to sam" → `send_reply` call |
| Integration | `backend/tests/integration/test_e2e_mode.py` | `test_reset_endpoint_only_in_e2e` | 404 in `test`, 204 in `e2e` |
| E2E | `frontend/e2e/core-flow.spec.ts` | 6 specs above | as listed |

**Run:**
```bash
make test
make lint
make build
make check-invariants
make e2e
```

**Manual verification:**
1. Run `make e2e` and open the HTML report (`pnpm exec playwright show-report`).
2. Manually walk the full real flow once more against real Gmail: search → reply (to yourself) → triage → archive one email → Send now digest.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated (Phase = "v1 complete")
