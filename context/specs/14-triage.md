# Unit 14: On-demand triage

## What to build
A `triage_inbox` agent tool that fetches recent inbox mail and uses the **fast model** with structured output to sort each email into Needs reply / Important / FYI / Low priority, each with a short reason. A `TriageCard` renders the groups in the chat.

## Why
This answers "what needs my attention?", the second core question users ask. The classification prompt and structured-output pattern are reused by digests (Unit 18).

## Scope
**In scope**
- `app/agent/triage.py` (classification chain), `app/agent/tools/triage.py` (tool), fast model in tool context, `ScriptedChatModel.with_structured_output` support.
- Frontend `TriageCard`.

**Out of scope (do not build in this unit)**
- Scheduled triage/digests (16–18). Acting on triage results automatically (user asks the agent explicitly).

## Prerequisites
- Unit 09 complete. (Independent of 12–13.)

## How to build it

### Backend
- `app/llm/fake.py`: `ScriptedChatModel.with_structured_output(schema)` returns a runnable that pops from `structured_responses: list[BaseModel]` (queued via `queue_structured(obj)`).
- `app/agent/context.py`: `ToolContext.fast_model: BaseChatModel`; `create_app` stores `app.state.fast_model = get_fast_model(settings)` and `services/chat.py` passes it in `configurable`.
- `app/agent/triage.py`:
  - `class TriageItem(BaseModel)`: `email_id: str`, `category: Literal["needs_reply","important","fyi","low"]`, `reason: str` (≤ 120 chars).
  - `class TriageResult(BaseModel)`: `items: list[TriageItem]`.
  - `TRIAGE_PROMPT`: definitions — needs_reply = a person is waiting on the user (direct question, request, scheduling); important = time-sensitive or from a frequent correspondent but no reply needed (bills due, approvals, deadlines); fyi = informational from real people/teams; low = newsletters, promotions, automated notifications. Input = numbered list of `id | from | subject | snippet | date`. Output one item per email.
  - `async def classify(fast_model, emails: list[EmailSummary]) -> TriageResult` — `fast_model.with_structured_output(TriageResult).ainvoke(...)`; drops items with unknown ids; emails missing from the output default to `fyi` with reason "Not classified".
- `app/agent/tools/triage.py`: `triage_inbox(hours: int = 24 (1..168), only_unread: bool = False, max_emails: int = 30 (1..50))` → query `in:inbox -category:promotions after:<epoch(now - hours)>` (+ ` is:unread`) — Gmail's Promotions category is excluded from the fetch to save tokens and is not mentioned in the result. Content for the agent: grouped compact lines with ids. Artifact: `{"type": "triage", "window_hours", "only_unread", "groups": [{"category", "items": [EmailSummary dict + "reason"]}]}` with groups in fixed order needs_reply, important, fyi, low, empty groups omitted.
- `TOOL_LABELS["triage_inbox"] = "triaging inbox · last {hours}h"`. Prompt guidance: use `triage_inbox` for "what needs my attention", "what's important", "catch me up"; after the card, summarise in 2–4 bullets the needs_reply items and offer to draft replies.

### Frontend
- `lib/sse-events.ts`: `TriageCardData`.
- `features/chat/cards/TriageCard.tsx`: header mono muted "triage · last 24h · 18 emails"; each group: header row with 2px left border colour per ui-context.md → Triage group colours, label + count; items = compact `EmailCard` variant with the reason line in `text-fg-muted text-xs` below the subject. Groups `fyi` and `low` collapsed by default (click header to expand). Registered in `cards/index.tsx`.

## Patterns, frameworks & concepts
- **Use:** fast model + `with_structured_output` (Pydantic) for classification; main model only for conversation.
- **Avoid:** one LLM call per email; fetching full bodies for triage (snippets only).
- **References:** architecture.md → Integrations (LLM); code-standards.md → LangGraph conventions.

## Design
Per ui-context.md → Triage group colours; dense rows; collapsed groups show "N emails" muted.

## Dependencies
None.

## Success criteria
- [ ] "What needs my attention today?" shows "triaging inbox · last 24h" then a TriageCard with sensible groups and reasons for real mail, followed by a short summary.
- [ ] "Triage unread from the last 3 days" passes `hours=72, only_unread=true`.
- [ ] An empty window gives "Nothing new in the last N hours" (empty groups → card shows that message).

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `tests/unit/agent/test_triage.py` | `test_classify_fills_missing_as_fyi` | output missing one id → that email in `fyi` "Not classified" |
| Unit | same | `test_classify_drops_unknown_ids` | hallucinated id ignored |
| Unit | same | `test_triage_tool_groups_in_fixed_order` | artifact group order needs_reply → low, empty omitted |
| Unit | same | `test_triage_query_built_from_args` | fake provider receives query containing `is:unread` and `after:` |
| Integration | `tests/integration/test_chat_triage.py` | `test_triage_tool_result_streamed` | `tool_result` with `ui.type == "triage"` |
| Unit | `src/features/chat/cards/TriageCard.test.tsx` | `renders groups with counts, fyi collapsed` | headers + counts; fyi items hidden until click |

**Run:**
```bash
make test
make lint
make build
```

**Manual verification:**
1. Ask "What needs my attention today?" → card + summary; spot-check categories against your inbox.
2. Ask "Draft a reply to the first one" → approval card (from Unit 13).

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
