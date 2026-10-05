# Unit 12: Reply & compose with approval (backend)

## What to build
Agent tools `lookup_contact`, `send_reply` and `compose_email`. The two send tools pause the graph with LangGraph `interrupt()` and emit an `approval_required` SSE event. A resume endpoint `POST /api/conversations/{id}/resume` takes Approve, Edit+Approve or Reject and continues the stream; only approval sends via `EmailProvider.send_message`. Every outcome is logged in `mail_actions`, and sent recipients update contacts.

## Why
This implements the core "draft, I approve sends" rule (Invariant 3) and covers both replies and new emails. Unit 13 renders the approval card on top of these events and endpoints. Unit 15 reuses the same interrupt/resume mechanism for archive/label.

## Scope
**In scope**
- `mail_actions` model + migration, `services/mail_actions.py`.
- `EmailProvider.send_message` (Gmail + Fake), `OutgoingEmail` type.
- Tools in `app/agent/tools/contacts.py` and `app/agent/tools/mail_send.py`; prompt guidance.
- SSE `approval_required`; resume endpoint; pending-approval in transcript; 409 on new message while approval pending.
- Contact counters updated on successful send.

**Out of scope (do not build in this unit)**
- Any UI (Unit 13). Attachments, forwarding, scheduled send, Gmail drafts (not in v1). Archive/label (Unit 15).

## Prerequisites
- Units 09 and 10 complete.

## How to build it

### Model + service
- `app/db/models/mail_action.py`: `MailAction` per architecture.md → Data Model (`action` CHECK in `send`,`archive`,`label`; `status` CHECK in `executed`,`rejected`,`failed`). Migration `mail_actions`.
- `services/mail_actions.py`: `async def record_action(session_factory, *, user_id, conversation_id, action, status, target_message_ids=(), recipients=(), subject=None, error=None) -> None` (own session + commit).
- `services/contacts.py`: `async def record_sent(session_factory, user_id, addresses: list[EmailAddress], at: datetime)` — upsert `sent_count + 1`, `last_interaction_at`, `display_name` if null; new rows `source="auto"`.
- `services/contacts.py`: `async def lookup(db, user_id, query: str, limit=5) -> list[Contact]` — excludes `is_automated`; exact email match first, then `ILIKE` on name/email ordered by `sent_count + received_count DESC`.

### Provider
- `app/email/types.py`: `OutgoingEmail(to: list[EmailAddress], cc: list[EmailAddress], subject: str, body_text: str, thread_id: str | None = None, in_reply_to: str | None = None, references: str | None = None)`.
- `EmailProvider.send_message(email: OutgoingEmail) -> str` (returns sent message id).
- Gmail: build `email.message.EmailMessage` (From = profile email, To, Cc, Subject, `In-Reply-To`, `References`, text/plain UTF-8 body); `raw = base64.urlsafe_b64encode(bytes)`; `users().messages().send(userId="me", body={"raw": raw, "threadId": thread_id?})`.
- Fake: appends to `self.sent: list[OutgoingEmail]`, returns `"fake-sent-<n>"`.

### Tools — `app/agent/tools/contacts.py`
- `lookup_contact(query: str)` → content lists up to 5 matches `"Priya Kumar <priya@acme.com> (sent 12, received 30)"` or `"No contacts match '<query>'"`; artifact `{"type": "none"}`.

### Tools — `app/agent/tools/mail_send.py`
- Shared `class SendDecision(TypedDict)`: `decision: Literal["approve","reject"]`, `edits: NotRequired[{to?: list[str], cc?: list[str], subject?: str, body?: str}]`.
- `send_reply(thread_id: str, body: str, reply_all: bool = False, cc: list[str] = [])`:
  1. Read-only prep: `provider.get_thread(thread_id)`. Target = latest message **not** from the user. To = its `From` (or `Reply-To` if present); if `reply_all`, add its To/Cc minus the user. Subject = `"Re: " + subject` unless it already starts with `re:` (case-insensitive). `in_reply_to` = target `message_id_header`; `references` = target references + its message id.
  2. `payload = {"type": "send_approval", "kind": "reply", "thread_id", "to": [...], "cc": [...], "subject", "body", "unknown_recipients": [addresses not in contacts]}`.
  3. `decision = interrupt(payload)` — **no side effects before this line.**
  4. Reject → `record_action(status="rejected")`; return content `"The user rejected this email. Do not resend unless they ask."`, artifact `{"type": "send_receipt", "status": "rejected", "to", "subject"}`.
  5. Approve → apply `edits` (validate every address with `pydantic.TypeAdapter(EmailStr)`; invalid → treat as failure with message), `send_message`, `record_action(status="executed")`, `record_sent`; return content `"Sent to <to> (message id …)"`, artifact `{"type": "send_receipt", "status": "sent", "to", "cc", "subject", "sent_at", "message_id"}`.
  6. `ProviderError` on send → `record_action(status="failed", error)`; artifact `status: "failed", error`; content tells the model sending failed and it may offer to try again. `ProviderAuthError` propagates.
- `compose_email(to: list[str], subject: str, body: str, cc: list[str] = [])` — `to` must be email addresses (schema validates `EmailStr`, 1..20). Same steps 2–6 with `kind: "new"`, no thread.
- Register in `ALL_TOOLS`. `TOOL_LABELS`: `lookup_contact` → "looking up contact · {query}", `send_reply` → "drafting reply", `compose_email` → "drafting email".
- Prompt guidance: resolve people by name with `lookup_contact` before `compose_email`; if several plausible matches, ask the user which one (don't guess); never put a name in `to`; write drafts in the user's voice, concise, no signature placeholder text; after a rejection, ask what to change.

### Streaming + endpoints
- `schemas/stream.py`: `ApprovalRequiredEvent(interrupt_id: str, ui: dict[str, Any])`.
- `streaming.py`: on `updates` chunk with key `"__interrupt__"`, emit `approval_required` for each `Interrupt` (`id`, `value`), then `done`.
- `services/chat.py`:
  - `async def get_pending_interrupt(graph, config) -> Interrupt | None` — from `(await graph.aget_state(config)).interrupts` (or tasks' interrupts depending on the installed LangGraph version).
  - `start_turn` → if a pending interrupt exists raise `ConflictError("Approve or reject the pending action first")` (409, before streaming).
  - `async def resume_turn(db, user, conversation_id, req: ResumeRequest, graph, ...)` → ownership, lock, verify pending interrupt id == `req.interrupt_id` else 409 `conflict` "No matching pending approval"; stream `graph.astream(Command(resume={"decision": req.decision, "edits": req.edits}), config, ...)` through `stream_turn`.
  - `get_transcript` → `TranscriptOut` gains `pending_approval: {interrupt_id, ui} | None`.
- `schemas/stream.py`: `ResumeRequest(interrupt_id: str, decision: Literal["approve","reject"], edits: SendEdits | None)` where `SendEdits` = `to/cc: list[EmailStr] | None, subject: str (1..300) | None, body: str (1..20000) | None`.
- `api/chat.py`: `POST /api/conversations/{id}/resume` → `EventSourceResponse`.

## Patterns, frameworks & concepts
- **Use:** LangGraph human-in-the-loop — `interrupt()` inside the tool, `Command(resume=...)` to continue. Tools re-run from the top on resume, so everything before `interrupt()` must be read-only and deterministic.
- **Use:** audit log (`mail_actions`) for every mutation outcome (Invariant 3).
- **Avoid:** sending from anywhere except these tools and the digest self-send (Unit 18); accepting names (not addresses) as recipients; letting a new message bypass a pending approval.
- **References:** architecture.md → Data Flow (Approval), Invariants 3, 5, 6.

## Design
N/A — no UI changes (Unit 13). The current UI ignores the unknown `approval_required` event until then.

## Dependencies
None.

## Success criteria
- [ ] Via curl: "Reply to the latest email from <sender> saying thanks" streams `tool_start` (drafting reply) then `approval_required` with a correct To/Subject/body, then `done`; nothing is sent yet.
- [ ] `POST …/resume` with `approve` sends a real reply that appears threaded in Gmail Sent; a `mail_actions` row `send/executed` exists; the contact's `sent_count` increased.
- [ ] `reject` sends nothing and logs `rejected`; the assistant acknowledges.
- [ ] "Email <contact name> asking for the Q3 numbers" calls `lookup_contact` then `compose_email`; with two matching contacts it asks which one instead.
- [ ] Sending a new message while an approval is pending returns 409.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `tests/unit/agent/test_send_tools.py` | `test_reply_targets_latest_non_user_message` | fake thread with user's own last message → To = previous sender, subject "Re: …", in_reply_to set |
| Unit | same | `test_no_side_effects_before_interrupt` | run tool until interrupt → `fake.sent == []`, no `mail_actions` rows |
| Unit | `tests/unit/email/test_gmail_send.py` | `test_mime_has_threading_headers` | built MIME contains `In-Reply-To`, `References`, UTF-8 body |
| Integration | `tests/integration/test_send_approval.py` | `test_reply_interrupt_then_approve_sends` | scripted tool_call → `approval_required` event; resume approve → `fake.sent` has 1 email, receipt `sent`, `mail_actions` executed |
| Integration | same | `test_edits_are_applied` | resume with edited body/subject → sent email uses edits |
| Integration | same | `test_reject_sends_nothing` | `fake.sent == []`, `mail_actions` rejected |
| Integration | same | `test_invalid_edit_address_fails_safely` | edit to `"not-an-email"` → 422 at resume validation, nothing sent |
| Integration | same | `test_compose_flags_unknown_recipients` | `to=["new@x.com"]` → payload `unknown_recipients == ["new@x.com"]` |
| Integration | same | `test_send_failure_logged` | fake send raises `ProviderError` → receipt `failed`, `mail_actions` failed |
| Integration | same | `test_new_message_while_pending_conflicts` | 409 |
| Integration | same | `test_resume_wrong_interrupt_id_conflicts` | 409 |
| Integration | same | `test_transcript_includes_pending_approval` | `pending_approval.ui.type == "send_approval"` |
| Integration | same | `test_successful_send_updates_contact_counts` | `sent_count` +1 |
| Integration | `tests/integration/test_contacts_lookup.py` | `test_lookup_excludes_automated_and_ranks` | newsletter excluded; higher-count contact first |

**Run:**
```bash
make test
make lint
```

**Manual verification (real Gmail — send to yourself or a test address):**
1. In the UI ask "Reply to my latest email from <me/test address> saying got it" → the assistant stops after "drafting reply" (no card yet).
2. `curl -N -b "ea_session=…" localhost:8000/api/conversations/<id>/messages` (GET transcript) → `pending_approval` present; copy `interrupt_id`.
3. `curl -N -b … -H 'content-type: application/json' -d '{"interrupt_id":"…","decision":"approve"}' localhost:8000/api/conversations/<id>/resume` → stream completes; check Gmail Sent (threaded).

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
