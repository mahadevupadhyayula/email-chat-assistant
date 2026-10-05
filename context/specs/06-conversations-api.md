# Unit 06: Conversations API

## What to build
The `conversations` table and authenticated CRUD endpoints: create, list (newest-updated first), get, rename and delete — all scoped to the current user.

## Why
Every chat turn (Unit 07) belongs to a conversation whose id is the LangGraph `thread_id`; the sidebar (Unit 08) lists them.

## Scope
**In scope**
- Model + Alembic revision, `services/conversations.py`, schemas, router.
- Delete removes the row (LangGraph thread deletion is added in Unit 07 when the checkpointer exists — leave a single call site `services/conversations.py:delete_conversation` that Unit 07 extends).

**Out of scope (do not build in this unit)**
- Messages/transcripts, streaming, auto-titling (Unit 07). Frontend wiring (Unit 08).

## Prerequisites
- Unit 03 complete.

## How to build it

### `app/db/models/conversation.py`
- `Conversation(Base, UUIDPkMixin, TimestampMixin)`, table `conversations`: `user_id` FK users CASCADE (index), `title: str` (String(120), default `"New chat"`). Composite index `(user_id, updated_at DESC)`.
- Alembic revision `conversations`.

### `app/schemas/conversations.py`
- `ConversationOut`: `id, title, created_at, updated_at`.
- `ConversationListOut`: `items: list[ConversationOut]`.
- `ConversationCreate`: `title: str | None = None` (trimmed, 1..120 if provided).
- `ConversationUpdate`: `title: str` (trimmed, 1..120).

### `app/services/conversations.py`
- `async def create_conversation(db, user_id, title: str | None) -> Conversation`
- `async def list_conversations(db, user_id, limit: int = 100) -> list[Conversation]` — `ORDER BY updated_at DESC`.
- `async def get_conversation(db, user_id, conversation_id) -> Conversation` — `NotFoundError` if missing or other user's.
- `async def rename_conversation(db, user_id, conversation_id, title) -> Conversation`
- `async def touch_conversation(db, conversation_id) -> None` — sets `updated_at = now()` (used by Unit 07).
- `async def delete_conversation(db, user_id, conversation_id) -> None`

### `app/api/conversations.py` (`prefix="/api/conversations"`)
- `POST /` → 201 `ConversationOut`
- `GET /` → `ConversationListOut`
- `GET /{conversation_id}` → `ConversationOut`
- `PATCH /{conversation_id}` → `ConversationOut`
- `DELETE /{conversation_id}` → 204

## Patterns, frameworks & concepts
- **Use:** service-layer ownership checks (Invariant 2) — every query includes `Conversation.user_id == user_id`.
- **Use:** 404 for other users' resources.
- **Avoid:** returning SQLAlchemy objects directly without `response_model`; business logic in the router.
- **References:** architecture.md → Data Model; code-standards.md → API / Server Logic.

## Design
N/A — no UI changes.

## Dependencies
None.

## Success criteria
- [ ] With the dev server and a signed-in browser, `fetch('/api/conversations', {method:'POST', credentials:'include', headers:{'content-type':'application/json'}, body:'{}'})` in DevTools returns a conversation titled "New chat"; `GET /api/conversations` lists it.
- [ ] Rename and delete work; another user cannot see, rename or delete it.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Integration | `tests/integration/test_conversations_api.py` | `test_create_default_title` | 201, title "New chat" |
| Integration | same | `test_list_orders_by_updated_desc` | after renaming older conversation it appears first |
| Integration | same | `test_rename_validates_length` | 121-char title → 422 `validation_error` |
| Integration | same | `test_rename_trims_whitespace` | `"  Plans  "` → `"Plans"` |
| Integration | same | `test_delete_then_get_404` | 204 then 404 |
| Integration | same | `test_other_user_gets_404` | `other_auth_client` GET/PATCH/DELETE → 404 each; list excludes it |
| Integration | same | `test_requires_auth` | unauthenticated list → 401 |

**Run:**
```bash
make test
make lint
```

**Manual verification:**
1. Use DevTools fetch calls (above) to create, list, rename and delete a conversation.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
