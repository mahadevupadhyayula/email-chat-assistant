# Unit 13: Approval card UI

## What to build
The inline `SendApprovalCard` that appears when the stream emits `approval_required` or the transcript has a `pending_approval`. It has editable To / Cc / Subject / Body fields plus Reject and "Approve & send" buttons, and resumes the stream through `/resume`. Also a `SendReceiptCard` that renders sent / rejected / failed outcomes in the transcript.

## Why
This is where the user approves or rejects every email. It completes the reply and compose features end to end in the app.

## Scope
**In scope**
- `lib/sse-events.ts`: `approval_required` event, `SendApprovalData`, `SendReceiptData`.
- `useChatStream`: `pendingApproval` state, `resume(decision, edits)`.
- `features/chat/cards/SendApprovalCard.tsx`, `SendReceiptCard.tsx`, `RecipientInput.tsx`.
- Composer disabled while an approval is pending.

**Out of scope (do not build in this unit)**
- Archive/label approval card (Unit 15). Rich-text editing, attachments (not v1).

## Prerequisites
- Units 08 and 12 complete; `pnpm gen:api`.

## How to build it

### Stream handling
- `approval_required` → `pendingApproval = {interruptId, ui}`; stream then ends with `done`.
- On transcript load, `pending_approval` from the server sets the same state (so reload restores the card).
- `resume(decision: "approve"|"reject", edits?)` → `postSse(\`/api/conversations/${id}/resume\`, {interrupt_id, decision, edits}, signal)` handled exactly like `send()` (tokens, tool events, errors, possibly another `approval_required`). The card shows a spinner on the clicked button until the first event arrives, then is replaced by the resulting receipt card once the transcript refetches.
- 409 from resume → error row "This approval is no longer pending." + invalidate transcript.

### `SendApprovalCard.tsx`
- Container per ui-context.md → Approval card (`bg-elevated border border-line-strong rounded-md`). Header: `Send` icon + "Approve reply" (`kind: reply`) or "Approve new email" (`kind: new`).
- Fields (dense label-left grid, labels `text-xs text-fg-muted w-14`):
  - To / Cc: `RecipientInput` — chips (mono 12px, `bg-hover rounded-sm`, `X` to remove) + text input that adds on Enter/comma/blur if valid email (zod `email()`); invalid input shows `text-error` hint "Not a valid email". Recipients in `unknown_recipients` show a `text-warning` chip border and tooltip "Not in your contacts".
  - Subject: `Input`.
  - Body: `Textarea` auto-grow (min 6 rows, max 20).
- Footer right: Reject (secondary) and "Approve & send" (default, `aria-label="Approve and send email to <first recipient>"`). Approve is disabled when To is empty or the subject/body is empty.
- `edits` sent only for changed fields.
- Keyboard: `⌘Enter` / `Ctrl+Enter` in the card triggers Approve.

### `SendReceiptCard.tsx`
- One row: `sent` → `CheckCircle2 text-success` "Sent to <to joined> · <time>" + subject muted; `rejected` → `XCircle text-fg-muted` "Not sent — rejected"; `failed` → `AlertCircle text-error` "Sending failed: <error>".
- Register `send_approval` (only via pending state, not as a stored card) and `send_receipt` in `cards/index.tsx`.

### Composer
- While `pendingApproval` exists: textarea disabled, placeholder "Approve or reject the pending email first".

## Patterns, frameworks & concepts
- **Use:** controlled form state local to the card, initialised from the payload; diff → `edits`.
- **Use:** the same SSE consumer path for `send` and `resume`.
- **Avoid:** sending without an explicit click; optimistic "Sent" before the server confirms.
- **References:** ui-context.md → Approval card, Accessibility; architecture.md → Data Flow (Approval).

## Design
- Exactly per ui-context.md → Approval card. Card width = chat column. Field rows `gap-2`; inputs `h-8`; body textarea `font-sans text-sm`.
- Loading: clicked button shows `Loader2`; both buttons disabled.
- Error from resume: ErrorRow beneath the card with Retry (re-sends the same decision).

## Dependencies
None.

## Success criteria
- [ ] "Reply to <sender> saying I'll send it tomorrow" shows the approval card with correct To/Subject/body.
- [ ] Editing the body then "Approve & send" sends the edited text; the card becomes "Sent to …" and Gmail shows it threaded.
- [ ] "Email <contact> about lunch Friday" shows "Approve new email"; an address not in contacts has a warning chip.
- [ ] Reject → "Not sent — rejected" and the assistant asks what to change.
- [ ] Reloading with a pending approval shows the card again; the composer is disabled until it's resolved.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `src/features/chat/cards/SendApprovalCard.test.tsx` | `renders payload fields` | To chips, subject, body populated |
| Unit | same | `sends only changed fields as edits` | edit body → `onDecision("approve", {body})` |
| Unit | same | `approve disabled without recipients` | removing all To chips disables Approve |
| Unit | same | `flags unknown recipients` | chip has warning class + tooltip text |
| Unit | `src/features/chat/cards/RecipientInput.test.tsx` | `adds valid email on enter, rejects invalid` | chip added / error shown |
| Unit | `src/features/chat/cards/SendReceiptCard.test.tsx` | `renders sent, rejected, failed` | correct text per status |
| Unit | `src/features/chat/useChatStream.test.tsx` | `approval_required sets pending and resume posts decision` | `postSse` called with `/resume` and body |
| Unit | `src/features/chat/ChatPage.test.tsx` | `composer disabled while approval pending` | textarea disabled |

**Run:**
```bash
cd frontend && pnpm test && pnpm lint && pnpm typecheck && pnpm build
make test
```

**Manual verification (send to yourself / a test address):**
1. Ask for a reply → edit → Approve → check Gmail Sent.
2. Ask to email a contact by name → card → Reject → assistant responds.
3. Trigger a card, reload the page → card restored.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
