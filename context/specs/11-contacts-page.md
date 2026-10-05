# Unit 11: Contacts page & manual contacts

## What to build
Endpoints to add, rename and delete manual contacts, and the `/contacts` page: searchable table of contacts with counts and last interaction, "Show automated" switch, sync status line with "Sync now", "Add contact" dialog, and per-row Rename/Delete.

## Why
Gives the user visibility and control over the contacts the assistant will use to resolve recipients when composing (Unit 12).

## Scope
**In scope**
- `POST /api/contacts`, `PATCH /api/contacts/{id}`, `DELETE /api/contacts/{id}`.
- `features/contacts/` page, table, dialogs, hooks; toasts via `sonner`.

**Out of scope (do not build in this unit)**
- Contact detail page, merging contacts, importing from Google Contacts (not in v1). Agent lookup (Unit 12).

## Prerequisites
- Units 04 and 10 complete.

## How to build it

### Backend
- `ContactCreate`: `email: EmailStr` (lowercased), `display_name: str | None` (trimmed, ≤200). `ContactUpdate`: `display_name: str` (trimmed, 1..200).
- `services/contacts.py`:
  - `create_manual_contact(db, user_id, data)` → if a row with that email exists → `ConflictError("Contact already exists")`; else insert `source="manual"`, counts 0, `is_automated=False`.
  - `rename_contact(db, user_id, contact_id, display_name)` — allowed for both sources. A rename survives later syncs because Unit 10's upsert never overwrites an existing non-null `display_name`.
  - `delete_contact(db, user_id, contact_id)` — only `source="manual"`; `auto` → `ConflictError("Synced contacts can't be deleted")`.
- Router: `POST /` 201 `ContactOut`; `PATCH /{id}` → `ContactOut`; `DELETE /{id}` → 204. Ownership → 404.

### Frontend — `src/features/contacts/`
- `pnpm dlx shadcn@latest add table dialog badge switch label sonner`; mount `<Toaster position="bottom-right" />` in `AppShell`.
- `pnpm add react-hook-form zod @hookform/resolvers`.
- `api.ts`/`hooks.ts`: `useContacts({q, includeAutomated})` (`useInfiniteQuery`, key `["contacts", q, includeAutomated]`), `useSyncStatus()` (polls every 3 s while `running`, else stops), `useStartSync()`, `useCreateContact()`, `useRenameContact()`, `useDeleteContact()` — all invalidate `["contacts"]`.
- `ContactsPage.tsx` (route `/contacts`, replaces ComingSoon): header per ui-context.md → Contacts. Search input debounced 250 ms. Sync status line: `never` → "Not synced yet"; `running` → `Loader2` "Syncing…"; `idle` → "Synced <relative time>"; `failed` → `text-error` "Sync failed: <last_error>".
- `ContactsTable.tsx`: columns Name (display_name or muted "—"), Email (mono), Sent, Received (mono, right-aligned), Last interaction (mono relative, e.g. "3d ago"), Source (`Badge` outline: `auto` / `manual`), row `DropdownMenu`: Rename (both), Delete (manual only). "Load more" ghost button when `next_cursor`.
- `ContactFormDialog.tsx`: mode add (Email + Name) / rename (Name only); zod schema `{ email: z.string().email(), display_name: z.string().max(200).optional() }`; server 409 shows field error "This contact already exists". Success → toast "Contact added" / "Contact renamed".
- Delete → `AlertDialog` "Delete <email>?" → toast "Contact deleted".

## Patterns, frameworks & concepts
- **Use:** `useInfiniteQuery` with server cursors; react-hook-form + zod.
- **Avoid:** client-side filtering of the full list; deleting auto contacts.
- **References:** ui-context.md → Contacts layout, States; code-standards.md → Error Handling.

## Design
- Per ui-context.md → Contacts. Table rows 40px, header `text-xs text-fg-muted uppercase tracking-wide`. Loading: 8 skeleton rows. Empty (no contacts, not syncing): `Users` icon, "No contacts yet", hint "Contacts appear after your mail syncs, or add one manually.", Add contact button. Empty search: "No contacts match "<q>"".

## Dependencies
- `sonner` (via shadcn) — toasts. `react-hook-form`, `zod`, `@hookform/resolvers` — forms.

## Success criteria
- [ ] `/contacts` lists synced contacts; search filters by name/email; "Show automated" reveals newsletter senders.
- [ ] "Sync now" shows "Syncing…" then "Synced just now".
- [ ] Add contact with a new email → appears with `manual` badge; adding an existing email shows "already exists".
- [ ] Rename works for both sources and survives a sync; Delete is only offered for manual contacts.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Integration | `tests/integration/test_contacts_api.py` | `test_create_manual_contact` | 201, source manual, email lowercased |
| Integration | same | `test_create_duplicate_conflict` | 409 `conflict` |
| Integration | same | `test_rename_auto_contact_survives_sync` | rename then sync → name kept |
| Integration | same | `test_delete_auto_contact_conflict` | 409 |
| Integration | same | `test_delete_manual_contact` | 204, gone |
| Integration | same | `test_other_user_404` | PATCH/DELETE → 404 |
| Unit | `src/features/contacts/ContactsPage.test.tsx` | `renders rows and sync status` | rows + "Synced" text |
| Unit | same | `delete only offered for manual` | auto row menu lacks Delete |
| Unit | `src/features/contacts/ContactFormDialog.test.tsx` | `validates email` | invalid email → error, no submit |
| Unit | same | `shows conflict error` | mocked 409 → "already exists" |

**Run:**
```bash
make test
make lint
make build
```

**Manual verification:**
1. Open Contacts → search a known name → found.
2. Add a manual contact, rename it, delete it.
3. Toggle "Show automated", click Sync now.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
