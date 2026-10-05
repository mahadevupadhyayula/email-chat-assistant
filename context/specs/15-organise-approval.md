# Unit 15: Organise with approval (archive & label)

## What to build
Agent tools `archive_emails` and `label_emails`. Each pauses on an `interrupt()` with a bulk approval payload listing every affected email. A `BulkApprovalCard` lets the user untick rows, then Approve or Reject. The provider gains label and modify operations, and an `ActionReceiptCard` shows the result.

## Why
Organising is the fourth-priority v1 capability ("archive all newsletters from this week"). It reuses the interrupt/resume flow from Units 12–13.

## Scope
**In scope**
- Provider: `get_summaries(ids)`, `list_labels()`, `create_label(name)`, `modify_labels(ids, add, remove)` (Gmail + Fake).
- Tools in `app/agent/tools/mail_organise.py`; `mail_actions` logging; `ResumeRequest.edits` extended with `message_ids`.
- Frontend `BulkApprovalCard`, `ActionReceiptCard`.

**Out of scope (do not build in this unit)**
- Delete/trash, mark read/unread, move between labels other than archive, removing labels (not in v1).

## Prerequisites
- Unit 13 complete.

## How to build it

### Provider
- `get_summaries(ids: list[str]) -> list[EmailSummary]` (batch metadata get; unknown ids skipped).
- `list_labels() -> list[Label(id, name, type)]`; `create_label(name) -> Label`; `modify_labels(message_ids, add_label_ids, remove_label_ids) -> None` using `users.messages.batchModify` (≤1000 ids). Archive = remove `INBOX`.
- Fake: in-memory labels and per-message label sets; records calls.

### Tools — `app/agent/tools/mail_organise.py`
- `archive_emails(message_ids: list[str] (1..100), reason: str)`; `label_emails(message_ids: list[str] (1..100), label_name: str (1..100), archive: bool = False)`.
- Pre-interrupt (read-only): `get_summaries(message_ids)`; for label, `list_labels()` to set `label_exists` (case-insensitive name match).
- Payload: `{"type": "bulk_approval", "action": "archive"|"label", "label_name"?: str, "label_exists"?: bool, "archive"?: bool, "reason": str, "items": [EmailSummary dicts]}`.
- `decision = interrupt(payload)`; approve → `ids = edits.message_ids ∩ original ids` (default all; empty → treated as reject); for label: create the label if missing, then `modify_labels(add=[label_id], remove=["INBOX"] if archive)`; archive: `modify_labels(remove=["INBOX"])`. Log `mail_actions` (`archive`/`label`, executed/rejected/failed, `target_message_ids`). Artifact `{"type": "action_receipt", "action", "status", "count", "label_name"?}`.
- Prompt guidance: find candidate emails with `search_emails` first, then call the organise tool with their ids; never more than 100 per call; tell the user how many were affected.
- `TOOL_LABELS`: "preparing archive · {n} emails", "preparing label · {label_name}".

### Resume schema
- Rename `SendEdits` → `ApprovalEdits` adding `message_ids: list[str] | None`. The send tools ignore `message_ids`; the organise tools ignore the send fields.

### Frontend
- `cards/BulkApprovalCard.tsx`: header icon `Archive` or `Tag`, title "Approve archive (N emails)" / "Approve label "<name>" (N emails)" + `Badge` "new label" if `!label_exists`, + "and archive" note if `archive`. Reason line muted. List of compact email rows each with a `Checkbox` (all checked); header "Select all" checkbox; list scrolls after 8 rows (`max-h-80`). Footer: Reject (secondary), Approve (default, label "Archive N" / "Label N", N = checked count, disabled at 0). Edits: `message_ids` only if some were unchecked.
- `cards/ActionReceiptCard.tsx`: `executed` → `CheckCircle2` "Archived 12 emails" / "Labelled 5 emails as Clients"; `rejected` → "No changes made"; `failed` → error.
- `useChatStream`/pending approval rendering picks `SendApprovalCard` vs `BulkApprovalCard` by `ui.type`.
- `pnpm dlx shadcn@latest add checkbox`.

## Patterns, frameworks & concepts
- **Use:** same interrupt/resume flow + audit log as Unit 12 (Invariant 3).
- **Use:** intersect edited ids with the original ids server-side (never trust client-added ids).
- **Avoid:** acting on ids that weren't in the approval payload; per-message API calls when `batchModify` works.

## Design
Per ui-context.md → Approval card; rows reuse compact EmailCard styling with a leading checkbox.

## Dependencies
- shadcn `checkbox` (via CLI).

## Success criteria
- [ ] "Archive newsletters from this week" → search → BulkApprovalCard listing them; untick one → Approve → the others leave the Gmail inbox, the unticked one stays.
- [ ] "Label emails from <client> as Clients" with a new label → card shows "new label"; after approval the label exists in Gmail on those emails.
- [ ] Reject → "No changes made", `mail_actions` row `rejected`.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `tests/unit/agent/test_organise_tools.py` | `test_no_side_effects_before_interrupt` | fake has no modify/create calls before resume |
| Integration | `tests/integration/test_organise_approval.py` | `test_archive_subset` | edits.message_ids subset → only those lose `INBOX` |
| Integration | same | `test_client_added_ids_ignored` | extra id in edits not modified |
| Integration | same | `test_label_creates_missing_label` | label created once, applied |
| Integration | same | `test_reject_makes_no_changes` | no modify calls; `mail_actions` rejected |
| Integration | same | `test_empty_selection_treated_as_reject` | `message_ids: []` → rejected |
| Unit | `src/features/chat/cards/BulkApprovalCard.test.tsx` | `unticking updates count and edits` | button "Archive 2"; decision edits ids |
| Unit | same | `approve disabled when none selected` | disabled |
| Unit | `src/features/chat/cards/ActionReceiptCard.test.tsx` | `renders executed label receipt` | "Labelled 5 emails as Clients" |

**Run:**
```bash
make test
make lint
make build
```

**Manual verification:**
1. Archive a few promo emails via chat with one unticked → verify in Gmail.
2. Label two emails with a new label → verify in Gmail, then remove the label manually.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
