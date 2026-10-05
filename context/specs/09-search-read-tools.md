# Unit 09: Search & read tools

## What to build
The first agent tools — `search_emails` and `get_thread` — wired into the graph, new SSE events `tool_start` and `tool_result`, tool cards persisted in the transcript, and frontend rendering of a tool status row, `EmailListCard` (email cards) and `ThreadCard` inside assistant messages.

## Why
This delivers the product's moment of value: ask a question about the inbox and get a correct answer with the source emails shown. The tool/card plumbing built here is reused by every later tool.

## Scope
**In scope**
- `app/agent/tools/mail_read.py` (2 tools), tool guidance in the system prompt.
- Streaming of `tool_start`/`tool_result` (`stream_mode=["messages", "updates"]`).
- Transcript mapping: tool artifacts attached as `cards` to the assistant turn that produced them.
- Frontend: `ToolStatusRow`, `EmailCard`, `EmailListCard`, `ThreadCard`, card registry `cards/index.tsx`.

**Out of scope (do not build in this unit)**
- Clicking a card to open a thread pane (not in v1). Contact lookup (Unit 12). Triage (14).

## Prerequisites
- Unit 08 complete.

## How to build it

### Backend — `app/agent/tools/mail_read.py`
- `class SearchEmailsArgs(BaseModel)`: `query: str` (Gmail search syntax, 1..500 chars, described for the model with examples `from:priya newer_than:7d`, `subject:invoice after:2026/09/01`, `is:unread`), `max_results: int = 10` (1..25).
- `@tool("search_emails", args_schema=SearchEmailsArgs, response_format="content_and_artifact") async def search_emails(query, max_results, config: RunnableConfig)` → `ctx.email_provider.search(...)`. Content (for the LLM): numbered compact lines `"[1] id=<id> thread=<thread_id> | 2026-09-30 | From: Priya K <priya@acme.com> | Subject: … | Snippet: …"`; if empty: `"No emails matched query: <query>"`. Artifact: `{"type": "email_list", "query": query, "items": [EmailSummaryOut-shaped dicts]}`.
- `class GetThreadArgs(BaseModel)`: `thread_id: str`.
- `@tool("get_thread", ...)` → `get_thread`. Content: thread subject + each message's date/from/to/body (bodies already truncated by the provider). Artifact: `{"type": "thread", "thread_id", "subject", "messages": [{id, from, to, date, snippet}]}` (no full bodies in the artifact to keep checkpoints small).
- `ProviderAuthError` / `ProviderError` propagate (do not swallow) so the stream emits the right `error` code; `NotFoundError` from `get_thread` returns content `"Thread <id> not found"` with an empty artifact `{"type": "none"}` so the agent can recover.
- Register both in `ALL_TOOLS`.
- `prompts.py`: append tool guidance — use `search_emails` with Gmail query syntax; prefer narrow queries; use `get_thread` before quoting or summarising a specific conversation; refer to emails by sender + subject, never by raw id; if nothing found say so and show the query used.

### Backend — streaming
- `app/schemas/stream.py`: add `ToolStartEvent(tool_call_id: str, name: str, label: str)` and `ToolResultEvent(tool_call_id: str, name: str, ui: dict[str, Any])`.
- `app/agent/streaming.py`: switch to `stream_mode=["messages", "updates"]`. From `updates` of node `agent`: for each `tool_call` in the new `AIMessage` emit `tool_start` with a human label from `TOOL_LABELS` (`search_emails` → `"searching mail · {query}"`, `get_thread` → `"reading thread"`). From `updates` of node `tools`: for each `ToolMessage` emit `tool_result` with `ui = message.artifact` (skip when artifact `type == "none"`). Token streaming unchanged (only chunks from node `agent`).
- `app/services/chat.py:get_transcript`: group messages into turns — each `HumanMessage` starts a turn; the assistant transcript item for the turn concatenates final AI text and collects `cards` = artifacts of `ToolMessage`s in that turn, in order. `TranscriptMessageOut` gains `cards: list[dict[str, Any]] = []`.

### Frontend
- `lib/sse-events.ts`: add `tool_start` and `tool_result` variants; card union type `Card = EmailListCardData | ThreadCardData` (shapes mirror artifacts above).
- `useChatStream`: pending assistant gains `tools: {id, label, done}[]` and `cards: Card[]`; `tool_start` adds a running tool; `tool_result` marks it done and appends `ui` to `cards`.
- `features/chat/ToolStatusRow.tsx`: `font-mono text-xs text-fg-muted`, `Loader2` spinning while running, `Check` when done; label text truncated to one line.
- `features/chat/cards/EmailCard.tsx`: layout per ui-context.md → Email card (sender name, address mono muted, date mono right — `Intl.DateTimeFormat` "Sep 30" or time if today — unread dot `bg-unread size-1.5 rounded-full`, subject, snippet truncated).
- `features/chat/cards/EmailListCard.tsx`: header `text-xs font-mono text-fg-muted` "query: <query> · N results"; first 5 `EmailCard`s, then ghost button "Show N more"; zero items → muted line "No emails matched".
- `features/chat/cards/ThreadCard.tsx`: subject + message count header; compact rows (from · date · snippet).
- `features/chat/cards/index.tsx`: `renderCard(card: Card)` switch on `card.type`; unknown types render nothing.
- `AssistantMessage` renders tool rows (pending only), then Markdown text, then cards below the text with `gap-2`.

## Patterns, frameworks & concepts
- **Use:** `response_format="content_and_artifact"` — compact text for the model, structured artifact for the UI (code-standards.md → LangGraph conventions).
- **Use:** card registry keyed by `ui.type` so later units add card types without touching message components.
- **Avoid:** putting full email bodies into artifacts; letting tools catch and hide provider auth errors; importing `googleapiclient` in tools (Invariant 5).
- **References:** architecture.md → Data Flow; ui-context.md → Email card, tool status row.

## Design
- Tool status row while running: `Loader2 size-3.5 animate-spin` + mono label; becomes `Check` in `text-success` when done; tool rows are not shown for reloaded transcripts.
- Email cards per ui-context.md; list max 5 visible; whole card is not clickable in v1 (no hover affordance other than `bg-hover`).

## Dependencies
None.

## Success criteria
- [ ] Asking "find emails from <real sender> this month" shows "searching mail · from:… after:…", then an answer with email cards for real messages.
- [ ] Asking "summarise my latest thread with <sender>" triggers `search_emails` then `get_thread` and gives a summary consistent with the actual thread.
- [ ] A query with no matches produces "I couldn't find…" plus the query used and an empty-result card.
- [ ] Reloading the page shows the same cards under the assistant answer.
- [ ] Revoked Gmail access → error row + Reconnect banner.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `tests/unit/agent/test_mail_read_tools.py` | `test_search_emails_content_and_artifact` | with `FakeEmailProvider`, `q=invoice` → content contains `billing@saas.com`; artifact type `email_list`, 1 item |
| Unit | same | `test_search_emails_empty` | content starts "No emails matched"; artifact items `[]` |
| Unit | same | `test_get_thread_not_found_is_recoverable` | content "Thread x not found", artifact type `none` |
| Unit | same | `test_provider_auth_error_propagates` | fake `fail_with=ProviderAuthError()` → raises |
| Integration | `tests/integration/test_chat_tools.py` | `test_tool_events_streamed` | scripted: AI tool_call `search_emails{query:"invoice"}` then AI text → events include `tool_start(name=search_emails)`, `tool_result(ui.type=email_list)`, tokens, `done` |
| Integration | same | `test_transcript_attaches_cards_to_turn` | transcript assistant item has 1 card of type `email_list` |
| Integration | same | `test_reauth_error_during_tool_emits_error_event` | `error` code `provider_reauth_required` then `done` |
| Unit | `src/features/chat/cards/EmailListCard.test.tsx` | `shows first five and expands` | 7 items → 5 cards + "Show 2 more"; click → 7 |
| Unit | `src/features/chat/cards/EmailCard.test.tsx` | `renders unread dot and sender` | unread → dot present; sender name + address visible |
| Unit | `src/features/chat/useChatStream.test.tsx` | `tool events produce tool rows and cards` | tool_start → running row; tool_result → done + card |

**Run:**
```bash
make test
make lint
make build
```

**Manual verification:**
1. Ask "What did <a real contact> email me about last week?" → status row, answer, cards.
2. Ask "Summarise the most recent thread with them" → thread read and summarised accurately.
3. Ask for something that doesn't exist → explicit no-results answer.
4. Reload → cards persist.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
