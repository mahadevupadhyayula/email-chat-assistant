# Unit 10: Contacts sync backend

## What to build
`contacts` and `contact_sync_state` tables, an `EmailProvider.list_message_headers` method, a metadata-only contacts sync service (12-month backfill, incremental from a watermark), a backfill triggered after Google login, and endpoints `GET /api/contacts` (search + automated filter + cursor pagination), `GET /api/contacts/sync-status` and `POST /api/contacts/sync`.

## Why
Contacts = everyone the user has emailed or received email from. The Contacts page (Unit 11) displays them and `lookup_contact` (Unit 12) resolves names to addresses for compose.

## Scope
**In scope**
- Models + migration, provider method (Gmail + Fake), `services/contact_sync.py`, `services/contacts.py` (list/search only), schemas, router, background trigger in OAuth callback and `POST /sync`.

**Out of scope (do not build in this unit)**
- Manual add/rename/delete (Unit 11). UI (Unit 11). Periodic sync in the worker (Unit 18). Updating counts on send (Unit 12).

## Prerequisites
- Unit 05 complete.

## How to build it

### Models (`app/db/models/contact.py`) + migration
- `Contact` (`contacts`): fields per architecture.md → Data Model. `email` String(320) lowercase; `display_name` String(200) nullable; `source` CHECK in (`auto`,`manual`); counts `int` default 0; `last_interaction_at` nullable; `is_automated` bool default false; `UniqueConstraint(user_id, email)`; index `(user_id, last_interaction_at DESC)`; trigram not needed — search uses `ILIKE`.
- `ContactSyncState` (`contact_sync_state`): `user_id` PK/FK, `status` CHECK in (`idle`,`running`,`failed`), `watermark` timestamptz nullable, `last_error` Text nullable, `updated_at`.

### Provider method
- `app/email/types.py`: `MessageHeaders(id: str, from_: EmailAddress | None, to: list[EmailAddress], cc: list[EmailAddress], date: datetime, is_list_mail: bool)` (`is_list_mail` = `List-Unsubscribe` or `List-Id` header present).
- `EmailProvider.list_message_headers(query: str, max_messages: int) -> AsyncIterator[MessageHeaders]` — Gmail: page through `messages.list(q=query, maxResults=500)` until `max_messages`, fetch `format=metadata` with headers `From, To, Cc, List-Unsubscribe, List-Id` in batches of 100. Fake: filter seeded messages with the same mini query language.

### `app/services/contact_sync.py`
- Constants: `BACKFILL_DAYS = 365`, `MAX_MESSAGES_PER_DIRECTION = 5000`.
- `def is_automated_address(email: str, is_list_mail: bool) -> bool` — true if `is_list_mail` or local part matches `^(no-?reply|do-?not-?reply|notifications?|mailer-daemon|bounce[s]?|newsletter|news|updates|alerts?)([+._-].*)?$`.
- `async def sync_contacts(session_factory, provider, user_id, user_email) -> SyncResult(received_seen, sent_seen, contacts_upserted)`:
  1. Lock: set state `running` (if already `running` and `updated_at` < 15 min old → return early, `SyncResult` zeros).
  2. `window_start = watermark or now - BACKFILL_DAYS`; `window_end = now` (captured at start). Query suffix `after:<epoch(window_start)> before:<epoch(window_end)>`.
  3. Received: `-in:sent -in:chats -in:spam -in:trash` + window → aggregate per sender address: `received_count += 1`, latest date, display name (most recent non-empty), automated flag (any list mail or pattern).
  4. Sent: `in:sent` + window → for every To/Cc address: `sent_count += 1`, latest date, display name. Sent recipients are never `is_automated` unless matched by the address pattern.
  5. Exclude `user_email` itself. Upsert with `INSERT … ON CONFLICT (user_id, email) DO UPDATE` adding counts, `last_interaction_at = GREATEST(...)`, `display_name = COALESCE(contacts.display_name, excluded.display_name)` (never overwrite an existing name — keeps manual names and user renames from Unit 11), `is_automated = contacts.is_automated OR excluded.is_automated` only for `source = auto`.
  6. Set `watermark = window_end`, status `idle`, `last_error = NULL`. On exception: status `failed`, `last_error = str(e)[:500]`, re-raise `ProviderAuthError`, swallow+log others.
- `async def run_sync_in_background(app_state, user_id)` — builds its own DB session + provider (via the same credential loading as `get_email_provider`) and calls `sync_contacts`; used by `BackgroundTasks`.

### `app/services/contacts.py`
- `async def list_contacts(db, user_id, q: str | None, include_automated: bool, cursor: str | None, limit: int = 50) -> tuple[list[Contact], str | None]` — filter `ILIKE %q%` on email or display_name; order `last_interaction_at DESC NULLS LAST, email`; opaque cursor = base64 of `(last_interaction_at, email)`.
- `async def get_sync_status(db, user_id) -> ContactSyncState | None`.

### API (`app/api/contacts.py`, `prefix="/api/contacts"`)
- `GET /?q=&include_automated=false&cursor=&limit=50` → `{"items": [ContactOut], "next_cursor"}`; `ContactOut`: `id, email, display_name, source, sent_count, received_count, last_interaction_at, is_automated`.
- `GET /sync-status` → `{"status": "idle"|"running"|"failed"|"never", "watermark", "last_error"}`.
- `POST /sync` → 202 `{"status": "running"}`; schedules `run_sync_in_background` via `BackgroundTasks`.
- OAuth callback (Unit 03 router): after successful login, `background_tasks.add_task(run_sync_in_background, request.app.state, user.id)`. Skipped when `APP_ENV` is `test`.

## Patterns, frameworks & concepts
- **Use:** watermark-based incremental sync with a closed `[after, before)` window so messages are never double-counted.
- **Use:** Postgres `ON CONFLICT DO UPDATE` upserts in batches of 500.
- **Avoid:** fetching message bodies (metadata only); storing message ids; running the backfill inside the request (use `BackgroundTasks`).
- **References:** architecture.md → Data Model, Integrations & Background Work; progress-tracker Open Questions (automated contacts, backfill window).

## Design
N/A — no UI changes (Unit 11).

## Dependencies
None.

## Success criteria
- [ ] After signing in again, within a few minutes `GET /api/contacts` returns real correspondents ordered by most recent interaction, with plausible sent/received counts.
- [ ] Newsletters/noreply senders are excluded unless `include_automated=true`.
- [ ] `POST /api/contacts/sync` twice in a row does not inflate counts (second run covers only the new window).
- [ ] `GET /api/contacts/sync-status` shows `running` during and `idle` after a sync.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `tests/unit/test_contact_sync_rules.py` | `test_is_automated_address` | `no-reply@x.com`, `notifications@github.com` true; `priya@acme.com` false; list mail true |
| Integration | `tests/integration/test_contact_sync.py` | `test_backfill_counts_sent_and_received` | fake seed → Priya received_count 2, Sam sent_count 1, owner excluded |
| Integration | same | `test_second_sync_does_not_double_count` | run twice → counts unchanged |
| Integration | same | `test_incremental_adds_new_messages` | add a fake message after first sync → count +1 |
| Integration | same | `test_manual_display_name_not_overwritten` | pre-existing manual contact keeps its name |
| Integration | same | `test_failure_sets_failed_state` | fake `fail_with=ProviderError()` → state `failed`, `last_error` set |
| Integration | `tests/integration/test_contacts_api.py` | `test_list_excludes_automated_by_default` | newsletter sender absent; present with flag |
| Integration | same | `test_search_matches_name_or_email` | `q=pri` returns Priya |
| Integration | same | `test_pagination_cursor` | limit 2 → next_cursor; second page disjoint |
| Integration | same | `test_contacts_scoped_to_user` | other user sees none |
| Integration | same | `test_sync_endpoint_returns_202` | 202 + status running |

**Run:**
```bash
make test
make lint
```

**Manual verification:**
1. Sign out and in again → wait → open `localhost:5173/api/contacts` → your real correspondents.
2. Open `/api/contacts?include_automated=true` → newsletters appear.
3. `POST /api/contacts/sync` from DevTools, then check counts unchanged.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
