# Unit 17: Digests UI

## What to build
The `/digests` list page (digest cards with schedule summary, focus preview, enabled switch, last-run badge) and the create/edit form at `/digests/new` and `/digests/:id`. The form has name, day pills, time, timezone, focus instructions, sender/label/keyword tag inputs, lookback hours, enabled, Save, Cancel and Delete.

## Why
Lets the user define and edit custom scheduled digests. Unit 18 makes them run and adds Send now and run history to the edit page.

## Scope
**In scope**
- `features/digests/`: `DigestsPage`, `DigestCard`, `DigestForm`, `TagInput`, `DayPicker`, hooks.
- Routes `/digests`, `/digests/new`, `/digests/:id` (replace ComingSoon).

**Out of scope (do not build in this unit)**
- Send now button, run history table (Unit 18). Digest preview (not v1).

## Prerequisites
- Units 04 and 16 complete; `pnpm gen:api`.

## How to build it
- `pnpm dlx shadcn@latest add toggle-group select` (reuse `switch`, `textarea`, `label`, `badge`, `alert-dialog` from earlier units).
- `hooks.ts`: `useDigests()` `["digests"]`, `useDigest(id)`, `useCreateDigest`, `useUpdateDigest`, `useToggleDigest` (optimistic update of `enabled`), `useDeleteDigest` — invalidate `["digests"]`.
- `DigestsPage.tsx`: header "Digests" + "Create digest" (default). Grid of `DigestCard`s (1 column, `gap-3`). Loading: 3 skeleton cards. Empty: `CalendarClock` icon, "No digests yet", hint "Get a scheduled email summary of the mail that matters.", Create button.
- `DigestCard.tsx`: `bg-surface border border-line rounded-md p-3`; row 1 name (14px fg) + `Switch` (aria-label "Enable <name>"); row 2 summary (mono xs muted) + "next: <local datetime>" when enabled; row 3 focus first line truncated; row 4 last run `Badge` (`success` → success colour outline, `failed` → error, none → "Never run" muted). Click (outside the switch) → `/digests/:id`.
- `DigestForm.tsx`: react-hook-form + zod schema mirroring `DigestScheduleIn` limits. Layout per ui-context.md → Digests form (640px single column). Fields:
  - Name `Input`.
  - Days `DayPicker` = `ToggleGroup type="multiple"` with 7 pills Mon…Sun; quick links "Weekdays" / "Every day" (ghost xs).
  - Time `Input type="time"` step 60.
  - Timezone `Select` with `Intl.supportedValuesOf("timeZone")`, default `Intl.DateTimeFormat().resolvedOptions().timeZone`; searchable via typed filter input at top of the list.
  - Focus instructions `Textarea` (6 rows) with placeholder "e.g. Emails from clients, invoices or payments, anything from my manager. Skip newsletters." and live character counter `n/2000` (mono xs).
  - Filters: three `TagInput`s (Enter/comma adds chip, Backspace on empty removes last, ≤20): Senders (placeholder "priya@acme.com or @acme.com"), Labels, Keywords. Helper text: "Filters narrow which emails are considered; focus tells the AI what matters."
  - Lookback hours `Input type="number"` 1–168.
  - Enabled `Switch`.
  - Footer: Save (default; spinner while saving), Cancel (ghost → `/digests`), Delete (destructive, edit only, `AlertDialog` confirm).
  - Server 422 → map `error` field details onto fields when present; otherwise ErrorRow at the top. Success → toast "Digest saved" and navigate to `/digests`.

## Patterns, frameworks & concepts
- **Use:** zod schema matching backend limits; optimistic toggle with rollback on error.
- **Avoid:** computing next run on the client (use `next_run_at` from the server).
- **References:** ui-context.md → Digests layout, States, Accessibility.

## Design
Per ui-context.md → Digests. Day pills `h-8 w-11 font-mono text-xs`, selected = `bg-brand-subtle text-brand border-brand`. Field labels `text-xs text-fg-muted`, field gap `gap-4`.

## Dependencies
- shadcn `toggle-group`, `select` (via CLI).

## Success criteria
- [ ] Create a digest "Morning clients" Mon–Fri 08:00 with focus and a sender filter → it appears on `/digests` with "Mon–Fri · 08:00 · <tz>" and a next run time.
- [ ] Editing and saving changes the card; toggling the switch disables it (next run disappears) without opening the form.
- [ ] Validation errors show inline (no days selected, empty focus).
- [ ] Delete removes it after confirmation.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `src/features/digests/DigestForm.test.tsx` | `requires at least one day and focus` | submit blocked, errors shown |
| Unit | same | `weekdays quick link selects Mon–Fri` | 5 pills pressed |
| Unit | same | `submits normalized payload` | `days_of_week [0..4]`, `time_of_day "08:00:00"`, filters arrays |
| Unit | `src/features/digests/TagInput.test.tsx` | `adds on enter/comma, removes on backspace` | chips update; max 20 enforced |
| Unit | `src/features/digests/DigestsPage.test.tsx` | `empty state and cards` | empty message; with data shows summary text |
| Unit | same | `toggle calls update optimistically` | switch flips immediately; mutation called |

**Run:**
```bash
cd frontend && pnpm test && pnpm lint && pnpm typecheck && pnpm build
make test
```

**Manual verification:**
1. Create, edit, toggle and delete digests in the UI; reload to confirm persistence.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
