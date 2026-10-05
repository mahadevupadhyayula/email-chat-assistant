# Unit 07: Agent core & streaming

## What to build
The provider-agnostic LLM factory (OpenAI first) with a scripted fake model for tests, a LangGraph agent graph (no tools yet) checkpointed in Postgres, LangSmith tracing, a streaming endpoint `POST /api/conversations/{id}/messages` that returns Server-Sent Events, and `GET /api/conversations/{id}/messages` that returns the stored transcript.

## Why
This is the core chat loop. Unit 08 wires the UI to it; Units 09+ add tools to the same graph.

## Scope
**In scope**
- `app/llm/` (factory, scripted fake, error classification).
- `app/agent/` (state, prompts, graph, checkpointer, streaming, context helper).
- SSE events `title`, `token`, `error`, `done`; transcript endpoint; auto-title from the first message; checkpoint deletion on conversation delete; per-conversation turn lock.

**Out of scope (do not build in this unit)**
- Any tools, `tool_start`/`tool_result`/`approval_required` events (Units 09, 12). Frontend (Unit 08). LLM-generated titles (not in v1).

## Prerequisites
- Units 05 and 06 complete. `OPENAI_API_KEY` available for manual testing.

## How to build it

### Settings / env (`.env.example` + `Settings`)
- `OPENAI_API_KEY=`, `LLM_MAIN_MODEL=openai:gpt-4.1`, `LLM_FAST_MODEL=openai:gpt-4.1-mini`, `LLM_TIMEOUT_SECONDS=60`, `LLM_MAX_RETRIES=2`, `LANGSMITH_TRACING=false`, `LANGSMITH_API_KEY=`, `LANGSMITH_PROJECT=email-assistant-chat`.
- In `test`/`e2e`, `LLM_MAIN_MODEL` and `LLM_FAST_MODEL` default to `fake:scripted`.

### `app/llm/fake.py`
- `class ScriptedChatModel(BaseChatModel)`: field `responses: list[AIMessage]` (consumed FIFO), `calls: list[list[BaseMessage]]` (records inputs). `_generate` pops the next response (or returns `AIMessage("(no scripted response)")`). `_stream`/`_astream` yield the popped message's content as `AIMessageChunk`s split on spaces (tool_calls carried in a single chunk via `tool_call_chunks`). `bind_tools(tools, **kw)` returns `self`. `_llm_type = "scripted"`. Helper `queue(*messages: AIMessage | str)`.

### `app/llm/factory.py`
- `def get_main_model(settings) -> BaseChatModel` and `def get_fast_model(settings) -> BaseChatModel`: if spec == `fake:scripted` → `ScriptedChatModel()`; else `init_chat_model(spec, timeout=settings.llm_timeout_seconds, max_retries=settings.llm_max_retries, api_key=...)` — the provider prefix (`openai:`) decides which key to pass (`OPENAI_API_KEY` for `openai`). Unknown provider prefix → `ValueError` at startup with a clear message.
- `app/llm/errors.py`: `def is_llm_error(exc: BaseException) -> bool` — true for exceptions whose class module starts with `openai`, `anthropic`, `httpx` or is `langchain_core.exceptions.LangChainException`. This is the only place that knows provider exception types.

### `app/agent/checkpointer.py`
- `async def open_checkpointer(database_url: str) -> tuple[AsyncPostgresSaver, AsyncConnectionPool]`: convert `postgresql+asyncpg://` → `postgresql://`; `AsyncConnectionPool(conninfo, max_size=10, kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row}, open=False)`; `await pool.open()`; `saver = AsyncPostgresSaver(pool)`; `await saver.setup()`.
- Created in `create_app` lifespan → `app.state.checkpointer`; pool closed on shutdown.

### `app/agent/state.py`
- `class AgentState(MessagesState): pass` (room to grow; no extra keys now).

### `app/agent/prompts.py`
- `SYSTEM_PROMPT_TEMPLATE` — the assistant is an email assistant for `{user_email}`; today is `{today}` (ISO date, weekday); answer only from tool results, never invent emails, senders, dates or content; say clearly when nothing was found; keep answers concise and use bullet lists for multiple items; never claim an email was sent, archived or labelled unless a tool result says so. (Later units append tool guidance.)
- `def build_system_prompt(user_email: str, now: datetime) -> str`.

### `app/agent/context.py`
- `@dataclass class ToolContext: user_id: UUID; user_email: str; email_provider: EmailProvider; session_factory: async_sessionmaker[AsyncSession]`
- `def get_tool_context(config: RunnableConfig) -> ToolContext` — reads `config["configurable"]`.

### `app/agent/graph.py`
- `def build_graph(checkpointer: BaseCheckpointSaver, model: BaseChatModel, tools: Sequence[BaseTool] = ()) -> CompiledStateGraph`.
- Node `agent`: `async def call_model(state, config)` → `ctx = get_tool_context(config)`; messages = `[SystemMessage(build_system_prompt(ctx.user_email, now))] + state["messages"]`; model = `model.bind_tools(tools)` if tools else model; `return {"messages": [await model.ainvoke(messages, config)]}`. System message is never stored in state.
- Edges: `START → agent`; if tools: `ToolNode(tools)` node `tools`, `add_conditional_edges("agent", tools_condition)`, `tools → agent`; else `agent → END`.
- In `create_app` lifespan: `app.state.main_model = get_main_model(settings)`, `app.state.graph = build_graph(app.state.checkpointer, app.state.main_model, ALL_TOOLS)` where `app/agent/tools/__init__.py` defines `ALL_TOOLS: list[BaseTool] = []`.

### `app/schemas/stream.py`
- Pydantic models: `TitleEvent(title: str)`, `TokenEvent(text: str)`, `ErrorEvent(code: str, message: str)`, `DoneEvent()`. `def sse(event: str, payload: BaseModel) -> dict` → `{"event": event, "data": payload.model_dump_json()}`.
- `SendMessageRequest(content: str)` trimmed, 1..8000 chars.
- `TranscriptMessageOut(id: str, role: Literal["user","assistant"], content: str)`, `TranscriptOut(items: list[TranscriptMessageOut])`.

### `app/agent/streaming.py`
- `async def stream_turn(graph, input, config) -> AsyncIterator[dict]`: iterate `graph.astream(input, config, stream_mode=["messages"])`; for `AIMessageChunk` from node `agent` with string content → `sse("token", TokenEvent(text))`. On `DomainError` → `error` with its code; on `is_llm_error(exc)` → `error` code `llm_error`, message "The AI model request failed. Try again."; any other exception → logged + `error` code `internal_error`. Always finish with `sse("done", DoneEvent())`. On `asyncio.CancelledError` (client disconnect) re-raise without yielding.

### `app/services/chat.py`
- Module-level `_locks: dict[UUID, asyncio.Lock]`.
- `async def start_turn(db, user, conversation_id, content, graph, provider, session_factory) -> AsyncIterator[dict]`: `get_conversation` (ownership); if lock held → `ConflictError("A response is already in progress")` (raised before streaming starts → HTTP 409); if title is "New chat" → set title to first 60 chars of content (single line, ellipsis if cut), commit, yield `title` event first; build config `{"configurable": {"thread_id": str(id), "user_id", "user_email", "email_provider", "session_factory"}, "run_name": "chat_turn", "metadata": {"conversation_id": str(id)}}`; yield from `stream_turn(graph, {"messages": [HumanMessage(content)]}, config)`; finally `touch_conversation` (own session) and release lock.
- `async def get_transcript(db, user_id, conversation_id, graph) -> list[TranscriptMessageOut]`: ownership check; `state = await graph.aget_state(config)`; map `HumanMessage` → user, `AIMessage` with non-empty text content → assistant; skip others. Ids from message `.id`.

### `app/api/chat.py`
- `POST /api/conversations/{conversation_id}/messages` → `EventSourceResponse(start_turn(...), ping=15)`.
- `GET /api/conversations/{conversation_id}/messages` → `TranscriptOut`.
- `deps.get_graph(request)` returns `request.app.state.graph`.

### Conversation delete
- `services/conversations.py:delete_conversation` gains a `checkpointer` parameter and calls `await checkpointer.adelete_thread(str(conversation_id))` after deleting the row; router passes `request.app.state.checkpointer`.

### LangSmith
- No code beyond env: LangChain reads `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` from the process env (`uvicorn --env-file` loads them). `tests/conftest.py` sets `os.environ["LANGSMITH_TRACING"] = "false"` before importing the app.

## Patterns, frameworks & concepts
- **Use:** LangGraph `StateGraph` + `MessagesState` + `AsyncPostgresSaver`; `thread_id = conversation.id`.
- **Use:** `stream_mode="messages"` for token streaming; SSE via `sse-starlette`.
- **Use:** dependency injection through `config["configurable"]` (no globals in tools/nodes).
- **Avoid:** importing `langchain_openai` or `openai` outside `app/llm/` (Invariant 5); storing the system prompt in state; running the graph without the per-conversation lock.
- **References:** architecture.md → Data Flow (Chat turn), Integrations; code-standards.md → LangGraph / LangChain Conventions.

## Design
N/A — no UI changes (Unit 08).

## Dependencies
- `langgraph`, `langchain`, `langchain-core`, `langchain-openai` — agent + models.
- `langgraph-checkpoint-postgres`, `psycopg[binary,pool]` — Postgres checkpointer.
- `sse-starlette` — SSE responses.

## Success criteria
- [ ] With `OPENAI_API_KEY` set, `curl -N -b "ea_session=<cookie>" -H 'content-type: application/json' -d '{"content":"Say hello in five words"}' localhost:8001/api/conversations/<id>/messages` streams `event: title`, several `event: token`, then `event: done`.
- [ ] `GET /api/conversations/<id>/messages` returns the user and assistant messages; a follow-up question ("what did I just ask?") is answered with context (checkpointer works).
- [ ] With LangSmith env set, the run appears in the `email-assistant-chat` project.
- [ ] With an invalid `OPENAI_API_KEY`, the stream emits `error` `llm_error` then `done`.
- [ ] Deleting the conversation removes its checkpoints (`select count(*) from checkpoints where thread_id = '<id>'` → 0).

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `tests/unit/llm/test_factory.py` | `test_fake_spec_returns_scripted_model` | `fake:scripted` → `ScriptedChatModel` |
| Unit | same | `test_unknown_provider_raises` | `nope:model` → `ValueError` |
| Unit | `tests/unit/llm/test_fake.py` | `test_scripted_model_streams_queued_text` | queued "hello there world" streams 3 chunks |
| Unit | `tests/unit/agent/test_prompts.py` | `test_system_prompt_includes_date_and_email` | both substrings present |
| Unit | `tests/unit/agent/test_streaming.py` | `test_llm_error_becomes_error_event` | graph stub raising `openai.AuthenticationError`-like exception (class module `openai`) → events `error(llm_error)`, `done` |
| Integration | `tests/integration/test_chat_api.py` | `test_send_message_streams_tokens_and_done` | scripted "Hi there" → parsed SSE events: `title`, `token`×2, `done` |
| Integration | same | `test_first_message_sets_title` | conversation title = first 60 chars of content |
| Integration | same | `test_transcript_returns_user_and_assistant` | after one turn → 2 items with roles user, assistant |
| Integration | same | `test_history_is_sent_to_model_on_second_turn` | second turn's `ScriptedChatModel.calls[-1]` contains the first Human + AI messages and the system message first |
| Integration | same | `test_concurrent_turn_returns_409` | lock held → 409 `conflict` |
| Integration | same | `test_other_user_cannot_send_or_read` | 404 for both endpoints |
| Integration | same | `test_delete_conversation_deletes_checkpoints` | `graph.aget_state` after delete has no messages |
| Integration | same | `test_content_validation` | empty content → 422 |

**Run:**
```bash
make test
make lint
```

**Manual verification:**
1. Create a conversation via DevTools fetch, then run the `curl -N` command above with your `ea_session` cookie value → tokens stream.
2. Ask a follow-up referencing the previous answer → it remembers.
3. Check LangSmith (if configured).

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
