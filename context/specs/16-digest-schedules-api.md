# Unit 16: Digest schedules API

## What to build
`digest_schedules` and `digest_runs` tables. Authenticated CRUD endpoints for digest schedules with strict validation (days, time, IANA timezone, focus, filters, lookback). A server-computed human `summary` and `next_run_at` on each schedule, and a read-only runs list endpoint.

## Why
Users define their own scheduled digests. The UI (Unit 17) edits these records and the worker (Unit 18) executes them.

## Scope
**In scope**
- Models + migration, `services/digest_schedules.py`, `services/schedule_rules.py` (pure), schemas, router `/api/digests`.

**Out of scope (do not build in this unit)**
- Running digests, Send now (Unit 18). UI (Unit 17). Natural-language or cron-string schedules (not v1).

## Prerequisites
- Unit 03 complete.

## How to build it

### Models + migration
- `DigestSchedule` and `DigestRun` per architecture.md → Data Model. `days_of_week` `ARRAY(SmallInteger)`; `time_of_day` `Time`; filters `ARRAY(Text)` default `{}`; `enabled` default true. `DigestRun.schedule_id` FK CASCADE; `trigger` CHECK (`schedule`,`manual`); `status` CHECK (`running`,`success`,`failed`). Index `(schedule_id, started_at DESC)`.

### `app/services/schedule_rules.py` (pure, no APScheduler)
- `DAY_NAMES = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]`.
- `def summarise(days: list[int], time_of_day: time, tz: str) -> str` — consecutive runs collapsed: `[0,1,2,3,4]` → "Mon–Fri", `[5,6]` → "Sat–Sun", all 7 → "Every day", `[0,2,4]` → "Mon, Wed, Fri"; output `"Mon–Fri · 08:00 · Europe/London"`.
- `def next_run_at(days, time_of_day, tz, now: datetime) -> datetime` — next local datetime on an allowed weekday at that time, strictly after `now`, returned in UTC; DST-correct via `zoneinfo`.
- `def to_cron_fields(days, time_of_day) -> dict[str, str | int]` — `{"day_of_week": "mon,tue,...", "hour": 8, "minute": 0}` (consumed by Unit 18).

### Schemas — `app/schemas/digests.py`
- `DigestScheduleIn`: `name` (trim, 1..80), `days_of_week: list[int]` (1..7 unique values in 0..6, sorted on save), `time_of_day: time` (seconds must be 0), `timezone: str` (must be in `zoneinfo.available_timezones()`), `focus_instructions` (trim, 1..2000), `filter_senders: list[str]` (≤20, each 1..100, trimmed lowercase — emails or domains like `@acme.com`), `filter_labels: list[str]` (≤20, 1..100), `filter_keywords: list[str]` (≤20, 1..100), `lookback_hours: int` (1..168, default 24), `enabled: bool = True`.
- `DigestScheduleOut`: all fields + `id, summary, next_run_at (null if disabled), last_run: {status, started_at, finished_at} | null, created_at, updated_at`.
- `DigestRunOut`: `id, trigger, status, email_count, error, started_at, finished_at`.

### Service + router (`prefix="/api/digests"`)
- `POST /` 201, `GET /` (ordered by name), `GET /{id}`, `PUT /{id}` (full replace), `PATCH /{id}/enabled` body `{enabled: bool}`, `DELETE /{id}` 204, `GET /{id}/runs?limit=20` → `{"items": [DigestRunOut]}` newest first.
- Limit 20 schedules per user → 409 `conflict` "Digest limit reached".
- All scoped by `user_id`; 404 for others.

## Patterns, frameworks & concepts
- **Use:** pure functions for schedule maths (fully unit-tested, reused by the worker).
- **Use:** `zoneinfo` + `tzdata` for IANA validation and DST handling.
- **Avoid:** storing cron strings; importing APScheduler here (Invariant 8 spirit — scheduling stays in the worker).

## Design
N/A — no UI changes (Unit 17).

## Dependencies
- `tzdata` — guarantees IANA timezone data on every platform.

## Success criteria
- [ ] Creating a digest via DevTools fetch returns `summary` like "Mon–Fri · 08:00 · Europe/London" and a correct `next_run_at`.
- [ ] Invalid timezone, empty days, or a 2001-char focus → 422 with field errors.
- [ ] Toggling enabled off makes `next_run_at` null.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `tests/unit/test_schedule_rules.py` | `test_summarise_ranges` | Mon–Fri, Sat–Sun, Every day, "Mon, Wed, Fri" |
| Unit | same | `test_next_run_same_day_later` | now Mon 07:00 local, time 08:00 → today 08:00 |
| Unit | same | `test_next_run_skips_to_allowed_day` | now Fri 09:00, days Mon–Fri 08:00 → Monday |
| Unit | same | `test_next_run_dst_transition` | Europe/London on DST change weekend → correct UTC offset |
| Unit | same | `test_to_cron_fields` | days [0,4] → "mon,fri" |
| Integration | `tests/integration/test_digests_api.py` | `test_create_and_get` | 201; summary + next_run_at present |
| Integration | same | `test_validation_errors` | bad tz, empty days, duplicate days, long focus → 422 |
| Integration | same | `test_disable_clears_next_run` | `next_run_at` null |
| Integration | same | `test_limit_20` | 21st → 409 |
| Integration | same | `test_runs_empty_list` | `items == []` |
| Integration | same | `test_other_user_404` | GET/PUT/DELETE → 404 |

**Run:**
```bash
make test
make lint
```

**Manual verification:**
1. Create, update, disable and delete a digest via DevTools fetch; check `summary`/`next_run_at`.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
