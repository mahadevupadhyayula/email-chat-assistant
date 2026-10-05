# Email Assistant Chat

## Overview
Email Assistant Chat is a locally-run web app where you manage Gmail by talking to an AI assistant. You ask questions ("what did Priya say about the contract?"), ask for triage ("what needs my attention today?"), have it draft replies or new emails, and have it archive or label mail in bulk — and nothing in the mailbox changes until you click Approve on an inline approval card. Separately, you define scheduled digests (days + time + focus topics + filters) that a background worker builds and emails to you. Today the user does all of this manually in the Gmail web UI, scrolling and searching by hand.

## Primary User
- **v1:** the builder themself — a single, technically capable professional with one Gmail account, running the app on their own machine.
- **Later (not v1):** busy professionals who sign up and connect their own inboxes. The architecture keeps `user_id` ownership and an `EmailProvider` interface from day one so this is an extension, not a rewrite.
- **Core need:** get answers, triage and replies out of a busy inbox in seconds, without losing control of what gets sent or changed.

## Goals
1. Answer a factual question about the inbox with the correct source thread cited as an email card, in under 15 seconds.
2. Go from "reply to X saying Y" (or "email Z about W") to a sent email in two clicks (Approve, or Edit → Approve).
3. Never change the mailbox without an explicit approval (except digest emails to the user's own address).
4. Deliver each enabled scheduled digest to the user's inbox within 2 minutes of its scheduled time.
5. Keep the code provider-agnostic: swapping the LLM provider is a config change; adding a mail provider is a new `EmailProvider` implementation.

## Core User Flow
1. **First visit:** user opens `http://localhost:5173`, sees the Login page with "Sign in with Google". Clicking it goes through Google consent (login + Gmail scopes) and lands back on the app.
2. **First landing:** a background contacts backfill starts. The user sees the chat screen with an empty conversation and 4 suggested prompts ("What needs my attention today?", "Summarise unread emails from the last 24h", "Find emails about invoices this month", "Draft a reply to my latest email").
3. **Ask:** user types a question and presses Enter. The assistant streams its answer token by token; while tools run, a compact "Searching mail…" status row shows the tool name. Cited emails render as email cards (sender, subject, date, snippet, unread dot) inside the message.
4. **Moment of value:** the answer is correct and the cited email card is the right thread.
5. **Reply / compose:** "Reply to the second one saying Thursday works" or "Email Priya asking for the Q3 numbers". The agent resolves recipients via contacts (asks if ambiguous), then the chat shows an **approval card**: To/Cc/Subject/Body editable, buttons Approve & send / Reject. Approve sends via Gmail; the card turns into a "Sent ✓" receipt. Reject tells the agent the user declined.
6. **Triage:** "What needs my attention?" returns a triage card grouping recent mail into Needs reply / Important / FYI / Low priority.
7. **Organise:** "Archive all newsletters from this week" shows an approval card listing affected emails (with per-row checkboxes). Approve applies the change to the checked ones.
8. **Contacts page:** lists everyone the user has emailed or received email from (name, email, sent/received counts, last interaction), searchable; user can add, rename or delete manual contacts and click "Sync now".
9. **Digests page:** user creates a digest — name, days of week, time, timezone, focus instructions, optional sender/label/keyword filters, lookback window — and toggles it on. At the scheduled time the worker emails "[Digest] <name> — <date>" to the user's own address.
10. **Return visits:** sidebar lists past conversations (newest first); clicking one restores the full transcript, including any pending approval card.

**Empty states:** no conversations → suggested prompts; no search results → the assistant says "I couldn't find any emails matching …" and shows the Gmail query it used; no contacts yet → "Contacts are syncing from your mail…" with spinner, then "No contacts yet" + Add button; no digests → "No digests yet" + "Create digest" button.

**Error paths:** Google token revoked/expired → API returns `provider_reauth_required`, a persistent banner shows "Gmail access expired — Reconnect" which restarts OAuth; LLM or Gmail call fails mid-stream → inline error row in the chat with "Retry" (re-sends the last user message); session expired → redirect to Login; approval of a send fails at Gmail → the card becomes a failed receipt showing the error, and the assistant offers to re-propose the same draft as a new approval card; digest run fails → recorded in run history with the error text, visible on the Digests page.

## Features

### Chat & conversations
- Streaming chat with the assistant (SSE), Markdown rendering for assistant text.
- Persistent conversations: create, list (sidebar), rename, delete; full transcript restore including pending approvals.
- Suggested prompts on empty conversations.

### Search & read (priority 1)
- Agent searches Gmail with Gmail query syntax and reads full threads.
- Results shown as email cards inside messages.

### Reply & compose with approval (priority 2)
- Reply within an existing thread (correct `In-Reply-To`/`References`/`threadId`).
- Compose a new email to one or more recipients (To, Cc), resolved via contacts.
- Every send pauses on an editable approval card; nothing is sent without Approve.

### Contacts
- Automatic contacts: everyone who sent the user an email or received at least one email from the user (backfill of last 12 months, then incremental).
- Per contact: display name, email, sent count, received count, last interaction, automated flag (noreply/list mail).
- Manual add, rename, delete (manual contacts only); search; "Show automated" toggle; "Sync now".
- Agent tool `lookup_contact` resolves names to addresses.

### Triage (priority 3)
- On-demand triage of recent mail into Needs reply / Important / FYI / Low priority with one-line reasons.

### Organise with approval (priority 4)
- Archive and label (existing or new label) multiple emails; approval card lists every affected email with per-row opt-out.

### Scheduled digests (priority 5)
- User-defined digests: name, days of week, time, IANA timezone, focus instructions, sender/label/keyword filters, lookback window (hours), enabled toggle.
- Delivered by email to the user's own address only. Run history (status, time, email count, error).
- "Send now" to test a digest immediately.

## Scope

### In Scope (v1)
- Single Google account per user, Gmail only, running locally (`localhost`).
- Everything listed under Features.
- Google OAuth app in "Testing" mode with the builder as test user.
- Provider-agnostic LLM layer with OpenAI configured first; LangSmith tracing (optional via env).

### Out of Scope (v1)
- Outlook / Microsoft Graph / generic IMAP providers (the `EmailProvider` interface is the seam for v2).
- Public multi-user signup, billing, Google OAuth app verification / CASA security review.
- Deployment / hosting / HTTPS; CI pipelines.
- Local mailbox mirror, embeddings or semantic search.
- Attachments — reading attachment contents or sending attachments.
- Forwarding emails, scheduling sends, snooze, delete/trash, mark read/unread.
- Light theme / theme toggle; mobile layouts below 1024px.
- Celery + Redis (the job functions are written scheduler-agnostic so they can move later).
- Digest delivery in-app; natural-language or raw-cron schedules.
- Product analytics, i18n, accessibility beyond the rules in ui-context.md.

## Success Criteria
1. A user can sign in with Google on `localhost:5173` and lands on the chat screen; signing out returns them to Login.
2. Asking "find emails from <real sender> this month" streams an answer and shows email cards for real matching messages.
3. "Reply to <thread> saying …" and "Email <contact name> about …" each produce an editable approval card; Approve sends a real email (visible in Gmail Sent, threaded correctly for replies); Reject sends nothing.
4. "What needs my attention?" returns a grouped triage card of recent mail.
5. "Archive these" / "Label these as Clients" produce an approval card; after Approve the change is visible in Gmail; unchecked rows are untouched.
6. The Contacts page lists real correspondents with counts after the initial sync; a manually added contact can be used by name in "Email <name> …".
7. A digest scheduled for a time 2 minutes ahead arrives in the user's inbox at that time with content matching its focus instructions, and appears as `success` in run history.
8. Revoking the app in Google account settings causes the "Reconnect" banner on the next Gmail action; reconnecting restores function.
