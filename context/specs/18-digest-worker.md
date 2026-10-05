# Unit 18: Digest worker

## What to build
A separate worker process (`make worker`) running APScheduler. It reconciles one cron job per enabled digest schedule from Postgres every 60 seconds and runs a scheduler-agnostic `run_digest` job. That job finds matching mail, summarises it with the fast model against the focus instructions, and emails the digest **only to the user's own address** through a guarded send. Each run is recorded in `digest_runs`. The worker also runs the 30-minute incremental contacts sync. The API gets `POST /api/digests/{id}/run` (Send now), and the edit page gets a Send now button and a run history table.

## Why
This delivers the scheduled half of triage, which the user asked for, and keeps contacts fresh.

## Scope
**In scope**
- `services/digests.py` (query building, summarisation, rendering, `send_digest_to_self`, `execute_digest_run`), `services/errors.py:SelfSendViolation`.
- `app/worker/runtime.py`, `app/worker/jobs/digest.py`, `app/worker/jobs/contacts.py`, `app/worker/main.py`.
- Send now endpoint + UI button + `RunHistory` table on `/digests/:id`.

**Out of scope (do not build in this unit)**
- Celery/Redis (later; the job functions are the seam). HTML emails (plain text in v1). In-app digest delivery (not v1). Retry policies beyond APScheduler misfire grace.

## Prerequisites
- Units 10, 16, 17 complete.

## How to build it

### `app/services/digests.py`
- `def build_digest_query(schedule, now) -> str` — `in:inbox -in:chats after:<epoch(now - lookback_hours)>` + ` (from:a OR from:b)` for senders (domain entries `@acme.com` → `from:acme.com`) + ` (label:x OR label:y)` (labels with spaces quoted) + ` ("kw one" OR kw2)` for keywords. Empty filter groups omitted.
- `class DigestItem(BaseModel)`: `email_id, thread_id, from_name, subject, why (≤160 chars)`; `class DigestSection(BaseModel)`: `title (≤60), items: list[DigestItem]`; `class DigestContent(BaseModel)`: `headline (≤120), sections: list[DigestSection] (≤6)`.
- `DIGEST_PROMPT` — given the user's focus instructions and a numbered list of emails (id, thread, from, subject, snippet, date), select only emails relevant to the focus, group them into short sections, explain in one line why each matters; if none are relevant return no sections. The focus text is user content: wrap it in `<focus>` tags and instruct the model to treat it as preferences, not as instructions to perform actions.
- `async def summarise(fast_model, schedule, emails) -> DigestContent` via `with_structured_output`; ids not in the input are dropped.
- `def render_digest_text(schedule, content, window_start, window_end, user_tz) -> tuple[subject, body]` — subject `"[Digest] <name> — <Mon 3 Oct>"`; body: headline, then each section title (uppercase) followed by `• <from_name> — <subject>\n  <why>\n  https://mail.google.com/mail/u/0/#all/<thread_id>`; empty → `"Nothing matched your focus in the last <N> hours."`; footer `"Schedule: <summary> · Edit at http://localhost:5173/digests/<id>"`.
- `def assert_self_recipient(user_email: str, email: OutgoingEmail) -> None` — raises `SelfSendViolation` unless `[a.email for a in email.to] == [user_email.lower()]` and `cc == []`.
- `async def send_digest_to_self(provider, user, subject, body) -> str` — builds `OutgoingEmail(to=[user.email])`, calls `assert_self_recipient`, then `provider.send_message`. **The only send path without approval (Invariant 4).**
- `async def execute_digest_run(runtime, schedule_id, trigger: Literal["schedule","manual"]) -> None` — insert `digest_runs(status="running")`; load schedule + user (skip with no run row if schedule deleted or disabled for `trigger="schedule"`); provider = runtime.provider_for(user_id); `search(query, limit=50)`; `summarise`; render; `send_digest_to_self`; update run `success`, `email_count = total items`, `sent_message_id`. Errors: `ProviderAuthError` → `failed`, error "Gmail access expired — reconnect in the app"; other → `failed`, `str(e)[:500]`, logged.

### `app/worker/runtime.py`
- `class WorkerRuntime` — holds settings, engine, session_factory, cipher, fast_model; `async def provider_for(user_id) -> EmailProvider` (same credential loading/refresh as the API; Fake in test/e2e). `async def create_runtime() / close()`. API reuses it for Send now via `app.state.runtime` (created in `create_app` lifespan).

### Jobs (no APScheduler imports — Invariant 8)
- `app/worker/jobs/digest.py`: `async def run_digest(schedule_id: str, trigger: str = "schedule") -> None` → `execute_digest_run(get_runtime(), UUID(schedule_id), trigger)`.
- `app/worker/jobs/contacts.py`: `async def sync_all_contacts() -> None` — for each user with `active` credentials, `sync_contacts(...)` sequentially; errors per user logged, not raised.

### `app/worker/main.py` (only APScheduler importer)
- `AsyncIOScheduler(timezone="UTC")`. On start: create runtime, add `IntervalTrigger(seconds=60)` job `reconcile` (also run once immediately) and `IntervalTrigger(minutes=30)` job `sync_all_contacts` (`next_run_time = now + 1 min`).
- `reconcile()`: load all enabled schedules; for each, job id `digest:<id>`; if missing or `updated_at` changed (track in a dict `id → updated_at`), `add_job(run_digest, CronTrigger(**to_cron_fields(...), timezone=schedule.timezone), args=[str(id)], id=..., replace_existing=True, misfire_grace_time=300, coalesce=True, max_instances=1)`; remove jobs whose schedule is gone or disabled.
- Graceful shutdown on SIGINT/SIGTERM (scheduler shutdown, runtime close). Log job adds/removes at INFO.
- Makefile: `worker: cd backend && uv run python -m app.worker.main`.

### API + UI
- `POST /api/digests/{id}/run` → 202 `{"status": "started"}`; `BackgroundTasks.add_task(execute_digest_run, request.app.state.runtime, id, "manual")`; ownership enforced first. Allowed even when disabled.
- `features/digests/RunHistory.tsx` on the edit page below the form: table (Started, Trigger, Status badge, Emails, Error truncated with tooltip), last 20 runs, polls every 3 s while any run is `running`. Empty: "No runs yet".
- "Send now" (secondary, `Send` icon) in the edit form footer → toast "Digest is being sent — check your inbox"; invalidates runs.

## Patterns, frameworks & concepts
- **Use:** scheduler-agnostic job functions + a thin APScheduler shell (Celery seam).
- **Use:** reconcile-from-DB loop instead of API→worker IPC; `coalesce` + `max_instances=1` to avoid duplicate sends.
- **Use:** prompt-injection hygiene — email content and focus text are data, wrapped in tags; the digest chain has no tools.
- **Avoid:** any recipient other than the user (Invariant 4); APScheduler imports in jobs (Invariant 8); running digests inside the API process on a schedule.

## Design
- RunHistory table per ui-context.md table rules (40px rows, mono timestamps); status badge colours: success → `text-success`, failed → `text-error`, running → `Loader2` + muted.

## Dependencies
- `apscheduler>=3.10,<4` — scheduling in the worker process.

## Success criteria
- [ ] With `make worker` running, a digest scheduled 2 minutes ahead arrives in your inbox at that time from and to your own address, with sections matching the focus; RunHistory shows `success`.
- [ ] "Send now" delivers a digest within a minute and shows a `manual` run.
- [ ] Disabling a digest removes its job within 60 s (worker log), and no email is sent at the scheduled time.
- [ ] Revoked Gmail → run `failed` with the reconnect message.
- [ ] Contacts `watermark` advances every 30 minutes while the worker runs.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `tests/unit/test_digests.py` | `test_build_query_with_filters` | contains `after:`, `(from:priya@acme.com OR from:acme.com)`, quoted label, keyword OR group |
| Unit | same | `test_build_query_without_filters` | only base + window |
| Unit | same | `test_assert_self_recipient_allows_self` | no exception |
| Unit | same | `test_assert_self_recipient_rejects_other_or_cc` | `SelfSendViolation` for other To, extra To, or any Cc |
| Unit | same | `test_render_empty_digest` | body contains "Nothing matched your focus" |
| Unit | same | `test_summarise_drops_unknown_ids` | hallucinated id removed |
| Unit | `tests/unit/test_worker_imports.py` | `test_jobs_do_not_import_apscheduler` | importing `app.worker.jobs.*` leaves `apscheduler` absent from `sys.modules` (fresh subprocess) |
| Integration | `tests/integration/test_digest_run.py` | `test_execute_run_sends_to_self_and_records_success` | fake sent 1 email to owner only; run `success`, `email_count` matches |
| Integration | same | `test_run_failure_recorded` | fake `fail_with=ProviderAuthError()` → run `failed` with reconnect message |
| Integration | same | `test_disabled_schedule_skipped_for_schedule_trigger` | no send, no run row |
| Integration | same | `test_send_now_endpoint` | 202; run row `manual` |
| Integration | same | `test_send_now_other_user_404` | 404 |
| Integration | `tests/integration/test_worker_reconcile.py` | `test_reconcile_adds_updates_removes_jobs` | in-memory `AsyncIOScheduler` (not started): job added, replaced on update, removed on disable |
| Unit | `src/features/digests/RunHistory.test.tsx` | `renders runs and empty state` | rows / "No runs yet" |

**Run:**
```bash
make test
make lint
make build
```

**Manual verification:**
1. `make worker` in a third terminal.
2. Create a digest for today, 2 minutes from now, focus "anything from real people". Wait → email arrives; RunHistory `success`.
3. Click Send now → second email, `manual` run.
4. Disable → watch the worker log remove the job.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
