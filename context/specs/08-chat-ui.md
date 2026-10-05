# Unit 08: Chat UI wired

## What to build
The real chat experience: the sidebar lists real conversations (new, rename, delete), `/c/:conversationId` loads the transcript and streams new assistant replies token by token over SSE, with Markdown rendering, suggested prompts on empty conversations, Stop, inline error + Retry, and a global "Reconnect Gmail" banner for `provider_reauth_required`.

## Why
This is the first unit where the user can actually chat with the assistant in the app. Card rendering (09, 13, 14, 15) plugs into the message components built here.

## Scope
**In scope**
- `lib/sse.ts` (POST-capable SSE parser) + `lib/sse-events.ts` types.
- `features/chat/`: `ChatPage`, `MessageList`, `MessageBubble`, `AssistantMessage`, `Composer`, `SuggestedPrompts`, `ErrorRow`, `useChatStream`, conversation hooks.
- Sidebar wired to `/api/conversations` (replaces `PLACEHOLDER_CONVERSATIONS`), New chat (+ `⌘K`), rename (inline), delete (confirm dialog).
- `/` route: redirect to the most recent conversation, or create one if none.
- `ReconnectBanner` in `AppShell` driven by `me.gmail_status === "revoked"` or any `provider_reauth_required` error.

**Out of scope (do not build in this unit)**
- Tool status rows and cards (Unit 09+). Approval cards (Unit 13). Message editing/regeneration (not in v1).

## Prerequisites
- Units 04 and 07 complete. Run `pnpm gen:api` to pick up conversation/chat schemas.

## How to build it

### `src/lib/sse-events.ts`
- `type StreamEvent = { event: "title"; data: { title: string } } | { event: "token"; data: { text: string } } | { event: "error"; data: { code: string; message: string } } | { event: "done"; data: Record<string, never> }`. Mirrors `backend/app/schemas/stream.py`.

### `src/lib/sse.ts`
- `async function* postSse(path: string, body: unknown, signal: AbortSignal): AsyncGenerator<StreamEvent>` — `fetch` POST with `credentials: "include"`, `accept: text/event-stream`; non-2xx → parse error envelope and throw `ApiError`; read `response.body` with `TextDecoder`, split on blank lines, parse `event:` and `data:` lines (multi-line data joined with `\n`), ignore comments/pings (`:`), `JSON.parse` data, yield typed events. Unknown event names are skipped.

### `src/features/chat/api.ts` + `hooks.ts`
- `listConversations`, `createConversation`, `renameConversation`, `deleteConversation`, `getTranscript` via `api()`.
- `useConversations()` (`["conversations"]`), `useCreateConversation()`, `useRenameConversation()`, `useDeleteConversation()` (invalidate `["conversations"]`; on deleting the open conversation navigate to `/`), `useTranscript(id)` (`["transcript", id]`).

### `src/features/chat/useChatStream.ts`
- State: `pending: { userText: string; assistantText: string; status: "streaming" | "error" | "idle"; error?: {code, message} }`.
- `send(text)`: sets pending, creates `AbortController`, iterates `postSse(\`/api/conversations/${id}/messages\`, {content: text}, signal)`; `title` → update `["conversations"]` cache entry; `token` → append; `error` → status `error` (+ if `provider_reauth_required` call `setReauthRequired(true)` from `ReconnectContext`); `done` → invalidate `["transcript", id]` and `["conversations"]`, then clear pending once the refetched transcript contains the new messages.
- `stop()`: abort controller; keep partial text visible with muted "(stopped)" suffix; invalidate transcript.
- `retry()`: re-sends the last user text.
- HTTP 409 → error row "A response is already in progress."

### Components (`src/features/chat/`)
- `ChatPage.tsx`: header (title; click → inline `Input` rename; Enter saves, Esc cancels), `MessageList`, `Composer`. Empty transcript and no pending → `SuggestedPrompts`.
- `MessageList.tsx`: `ScrollArea`; renders transcript items then pending user + pending assistant. Auto-scroll to bottom on new tokens unless the user has scrolled up more than 80px. `aria-live="polite"` on the streaming message.
- `MessageBubble.tsx` (user): right-aligned `bg-elevated rounded-md p-3 max-w-[80%] text-fg whitespace-pre-wrap`.
- `AssistantMessage.tsx`: `react-markdown` + `remark-gfm`, `max-w-[72ch]`, prose styles via component overrides (links `text-brand underline`, code `font-mono text-xs bg-hover rounded-sm px-1`, lists with `list-disc pl-5`). Streaming caret: 2px × 14px `bg-brand` blinking span appended while streaming. Links open in new tab with `rel="noreferrer"`.
- `Composer.tsx`: shadcn `Textarea` (add via CLI) auto-growing to 8 lines, placeholder "Ask about your email…", Enter sends (trimmed, non-empty), Shift+Enter newline; send button `ArrowUp` (default variant, icon-only, `aria-label="Send message"`) disabled while empty/streaming; while streaming shows Stop (`Square`, secondary, `aria-label="Stop generating"`); `Esc` stops.
- `SuggestedPrompts.tsx`: empty state (icon `Sparkles`, "Ask anything about your inbox") + 2×2 grid of secondary buttons with the four prompts from project-overview.md; click sends immediately.
- `ErrorRow.tsx`: error row style from ui-context.md with message and optional Retry button.

### Sidebar + routing
- `Sidebar.tsx`: use `useConversations()`; loading → 6 `Skeleton` rows; empty → muted "No conversations yet". Row hover → `MoreHorizontal` `DropdownMenu` (Rename → inline input in row; Delete → `AlertDialog` "Delete conversation? This can't be undone." with destructive Delete). "New chat" enabled: creates conversation and navigates to `/c/:id`. Global `⌘K`/`Ctrl+K` listener does the same.
- `HomeRedirect.tsx` for `/`: after `useConversations` loads → navigate to first item, or create one and navigate.
- Remove `ChatPlaceholder.tsx`.

### Reconnect banner
- `src/components/layout/ReconnectContext.tsx`: context `{ reauthRequired: boolean; setReauthRequired }`. Initialised true when `me.gmail_status === "revoked"`.
- QueryClient `queryCache`/`mutationCache` `onError`: `isReauthError(e)` → set flag (wire via a small module-level setter registered by the provider).
- `ReconnectBanner.tsx`: `bg-warning-subtle text-warning h-10` row, `AlertTriangle` icon, "Gmail access expired." and a link-styled button "Reconnect" → `window.location.href = "/api/auth/google/login"`.
- Sidebar user menu gains "Reconnect Gmail" item (same action).

## Patterns, frameworks & concepts
- **Use:** optimistic pending message rendered from local state, then reconcile with the refetched server transcript (server is source of truth).
- **Use:** `AbortController` for Stop and on unmount/navigation.
- **Use:** TanStack Query cache updates for the title event instead of refetching.
- **Avoid:** `EventSource` (GET-only); `fetch` outside `lib/` (Invariant 9); `dangerouslySetInnerHTML` for Markdown.
- **References:** ui-context.md → Layout Patterns (Chat, Sidebar), States, Accessibility.

## Design
- Exactly per ui-context.md → Chat and Sidebar. Chat column `max-w-3xl mx-auto px-4`, header 48px with bottom border `border-line`.
- Loading transcript: 3 skeleton message blocks. Error loading transcript: ErrorRow with Retry. Not found (404) → empty state "Conversation not found" + "New chat" button.
- Streaming: blinking emerald caret; composer disabled except Stop.

## Dependencies
- `react-markdown`, `remark-gfm` — assistant Markdown.
- shadcn `textarea`, `alert-dialog` (via CLI).

## Success criteria
- [ ] Signing in lands on a conversation; "New chat" and `⌘K` create new ones that appear at the top of the sidebar.
- [ ] Typing a question streams the answer token by token with Markdown formatting; the sidebar title updates to the first message.
- [ ] Reloading the page restores the full transcript.
- [ ] Stop halts streaming mid-answer; Retry after an error re-sends the last message.
- [ ] Rename and delete (with confirmation) work from the sidebar; deleting the open conversation navigates to another.
- [ ] Clicking a suggested prompt sends it.
- [ ] With Gmail access revoked (and `gmail_status: revoked`), the Reconnect banner shows; clicking it restarts OAuth.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `src/lib/sse.test.ts` | `parses multiple events across chunk boundaries` | stream split mid-event yields `title`, `token`, `done` in order |
| Unit | same | `ignores ping comments and unknown events` | `: ping` and `event: foo` skipped |
| Unit | same | `throws ApiError on non-2xx` | 409 with envelope → `ApiError` code `conflict` |
| Unit | `src/features/chat/useChatStream.test.tsx` | `accumulates tokens and finishes` | mocked `postSse` → assistantText "Hi there", status settles |
| Unit | same | `sets reauth flag on provider_reauth_required` | error event → context flag true |
| Unit | `src/features/chat/Composer.test.tsx` | `enter sends, shift+enter newlines` | onSend called once with trimmed text; newline inserted otherwise |
| Unit | same | `shows stop while streaming` | Stop button present, send absent |
| Unit | `src/features/chat/ChatPage.test.tsx` | `shows suggested prompts for empty conversation` | 4 prompt buttons |
| Unit | same | `renders transcript markdown` | assistant `**bold**` renders `<strong>` |
| Unit | `src/components/layout/Sidebar.test.tsx` | `lists conversations and creates new` | items rendered; New chat calls create + navigates |
| Unit | same | `delete asks for confirmation` | dialog shown; confirm calls delete |

**Run:**
```bash
cd frontend && pnpm test && pnpm lint && pnpm typecheck && pnpm build
make test
```

**Manual verification:**
1. Sign in → chat; click "What needs my attention today?" → assistant streams a reply (no tools yet, so it will say it can't access mail yet — that's expected).
2. Ask "what did I just ask?" → correct; reload → transcript restored.
3. Start a long answer ("write 500 words about email"), press Stop.
4. Rename + delete conversations from the sidebar.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
