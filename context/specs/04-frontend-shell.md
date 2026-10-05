# Unit 04: Frontend shell & auth guard

## What to build
The dark, token-driven frontend foundation: design tokens + fonts, shadcn/ui setup, React Router routes, TanStack Query, a typed API client generated from OpenAPI, the Login page, a `RequireAuth` guard using `/api/auth/me`, and the authenticated `AppShell` with the Sidebar (placeholder conversation list, nav links, user menu with Sign out) and an empty chat placeholder.

## Why
Every UI unit renders inside this shell and uses its tokens, client and query setup. Signing in and out through the real UI becomes possible.

## Scope
**In scope**
- Tokens in `globals.css` exactly per ui-context.md; Inter + JetBrains Mono.
- shadcn init + primitives: `button`, `input`, `scroll-area`, `separator`, `tooltip`, `avatar`, `dropdown-menu`, `skeleton`.
- Routes: `/login`, `/` (placeholder chat area), `/c/:conversationId` (same placeholder), `/contacts` and `/digests` (placeholder "Coming soon" empty states).
- `lib/api/client.ts`, generated `schema.d.ts`, `features/auth/*`, `components/layout/AppShell.tsx`, `Sidebar.tsx`.
- Remove the Unit 01 health `fetch` from `App.tsx`.

**Out of scope (do not build in this unit)**
- Real conversations data, chat composer or streaming (Unit 08). Reconnect banner (Unit 08). Contacts/Digests pages (11, 17).

## Prerequisites
- Unit 03 complete (`/api/auth/me`, `/api/auth/logout`, `/api/auth/google/login`).

## How to build it

### Tokens, fonts, shadcn
- `pnpm add @fontsource-variable/inter @fontsource/jetbrains-mono lucide-react react-router @tanstack/react-query` and `pnpm add -D openapi-typescript`.
- `pnpm dlx shadcn@latest init` (style new-york, base colour zinc, CSS variables yes, `src/styles/globals.css`, alias `@/components`, `@/lib/utils`). Then `pnpm dlx shadcn@latest add button input scroll-area separator tooltip avatar dropdown-menu skeleton`.
- `src/styles/globals.css`: define every token from ui-context.md under `:root` (dark values; dark-only), alias shadcn variables to them, and expose Tailwind v4 theme names via `@theme inline { --color-base: var(--bg-base); --color-surface: var(--bg-surface); --color-elevated: var(--bg-elevated); --color-hover: var(--bg-hover); --color-fg: var(--text-primary); --color-fg-secondary: var(--text-secondary); --color-fg-muted: var(--text-muted); --color-fg-disabled: var(--text-disabled); --color-brand: var(--accent-primary); --color-brand-hover: var(--accent-hover); --color-brand-foreground: var(--accent-foreground); --color-brand-subtle: var(--accent-subtle); --color-line: var(--border-default); --color-line-strong: var(--border-strong); --color-error: var(--state-error); --color-error-subtle: var(--state-error-subtle); --color-warning: var(--state-warning); --color-warning-subtle: var(--state-warning-subtle); --color-success: var(--state-success); --color-info: var(--state-info); --color-unread: var(--unread-dot); --font-sans: "Inter Variable", system-ui, sans-serif; --font-mono: "JetBrains Mono", ui-monospace, monospace; --radius-sm: 4px; --radius-md: 6px; --radius-lg: 8px; }` so classes `bg-surface`, `text-fg-muted`, `border-line`, `bg-brand`, `text-error` etc. exist. Body: `bg-base text-fg-secondary font-sans text-sm antialiased`. Add `.text-meta { font-size: 13px; line-height: 18px; }`.
- `index.html`: `<html lang="en" class="dark">`, title "Email Assistant".
- `main.tsx`: import fonts (`@fontsource-variable/inter`, `@fontsource/jetbrains-mono/400.css`) and `globals.css`.

### Typed API client — `src/lib/api/`
- `package.json` script `gen:api`: `openapi-typescript http://localhost:8000/openapi.json -o src/lib/api/schema.d.ts`. Commit the generated file.
- `errors.ts`: `class ApiError extends Error { status: number; code: string }`; `isReauthError(e)` → `code === "provider_reauth_required"`.
- `client.ts`: `async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T>` — prefixes nothing (paths start with `/api`), sets `credentials: "include"`, JSON body/headers when `json` provided, parses `{"error":{code,message}}` into `ApiError`, returns `undefined` for 204. Export typed helpers using `paths` from `schema.d.ts` where convenient (e.g. `type Me = components["schemas"]["MeResponse"]`).

### Auth feature — `src/features/auth/`
- `api.ts`: `getMe(): Promise<Me>`, `logout(): Promise<void>`.
- `hooks.ts`: `useMe()` (`queryKey ["me"]`, `retry: false`, `staleTime: 60_000`), `useLogout()` (on success `queryClient.clear()` then navigate `/login`).
- `LoginPage.tsx`: layout per ui-context.md → Login. Button is an `<a href="/api/auth/google/login">` styled as default Button (full-page navigation, not fetch). If `?error=oauth|state` show inline error row "Sign-in failed. Please try again." If `useMe` succeeds, redirect to `/`.
- `RequireAuth.tsx`: while loading → centred `Loader2`; on 401 `ApiError` → `<Navigate to="/login" replace />`; on other error → inline error row with Retry; on success renders `<Outlet />`.

### Router — `src/App.tsx`
```
/login                 → LoginPage
<RequireAuth>
  <AppShell>  (layout route)
    /                  → ChatPlaceholder
    /c/:conversationId → ChatPlaceholder
    /contacts          → ComingSoon title="Contacts"
    /digests           → ComingSoon title="Digests"
*                      → Navigate to "/"
```
- `main.tsx`: `QueryClientProvider` (defaults: `queries.retry = 1`, `refetchOnWindowFocus: false`), `BrowserRouter`, `TooltipProvider`.

### Layout — `src/components/layout/`
- `AppShell.tsx`: flex row, full height; `Sidebar` + `<main className="flex-1 min-w-0 bg-base">` with `<Outlet />`. Sidebar collapsed state in `localStorage` key `ea.sidebarCollapsed` (wrapped in try/catch); default collapsed when `window.innerWidth < 1280`.
- `Sidebar.tsx`: per ui-context.md → Sidebar. Conversation list uses a hard-coded `PLACEHOLDER_CONVERSATIONS` array of 5 `{id, title}` items (comment: replaced in Unit 08), rows link to `/c/:id`, active row styling from `useParams`. "New chat" button is present but disabled with tooltip "Available soon". Nav links use `NavLink` with active style. Footer: `Avatar` (image from `avatar_url`, fallback initials), email in mono, `DropdownMenu` with "Sign out" (calls `useLogout`).
- `ChatPlaceholder.tsx` (`src/features/chat/`): centred empty state — `MessageSquare` icon, "Start a conversation", hint "Chat arrives in the next units." 
- `ComingSoon.tsx` (`src/components/layout/`): empty state with given title.

## Patterns, frameworks & concepts
- **Use:** TanStack Query for all server state; `useMe` is the single source of auth truth.
- **Use:** generated OpenAPI types — never hand-copy backend schemas.
- **Use:** layout routes with `<Outlet />` for the shell.
- **Avoid:** `fetch` outside `lib/api/client.ts` (Invariant 9); raw hex colours or arbitrary colour classes; editing `components/ui/*`.
- **References:** ui-context.md (all sections); code-standards.md → Styling, TypeScript.

## Design
- Login, AppShell, Sidebar exactly per ui-context.md → Layout Patterns. Sidebar `bg-surface`, right border `border-line`; selected conversation `bg-brand-subtle` + 2px `--accent-primary` left border.
- Loading: centred `Loader2` for `useMe`; sidebar shows the placeholder list (no skeleton needed yet).
- Error: Login `?error` row uses the error row style.
- Min width 1024px; below 1280px sidebar starts collapsed, toggle button in the main area's top-left when collapsed.

## Dependencies
- `react-router`, `@tanstack/react-query`, `lucide-react`, `@fontsource-variable/inter`, `@fontsource/jetbrains-mono`, shadcn and its deps (installed by the shadcn CLI), dev `openapi-typescript`.

## Success criteria
- [ ] Visiting `localhost:5173` signed-out redirects to `/login` with the dark login screen.
- [ ] "Sign in with Google" completes OAuth and lands on the app shell showing your avatar/email in the sidebar footer.
- [ ] Clicking placeholder conversations changes the URL to `/c/<id>` and highlights the row; Contacts/Digests links show "Coming soon".
- [ ] Sign out returns to `/login`; navigating to `/` redirects to `/login` again.
- [ ] No raw hex colours in `src/` outside `globals.css` (`grep -rnE "#[0-9a-fA-F]{6}" src --include=*.tsx` returns nothing).

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `src/lib/api/client.test.ts` | `parses error envelope into ApiError` | 401 response with error JSON → throws `ApiError` with `code "unauthenticated"`, `status 401` |
| Unit | `src/lib/api/client.test.ts` | `sends credentials and json body` | fetch called with `credentials: "include"`, `content-type: application/json` |
| Unit | `src/features/auth/RequireAuth.test.tsx` | `redirects to login on 401` | with `getMe` mocked to reject `ApiError(401)` → login route rendered |
| Unit | `src/features/auth/RequireAuth.test.tsx` | `renders children when signed in` | outlet content visible |
| Unit | `src/features/auth/LoginPage.test.tsx` | `shows error from query param` | `/login?error=oauth` shows "Sign-in failed" |
| Unit | `src/components/layout/Sidebar.test.tsx` | `shows user email and sign out` | email visible; opening menu shows "Sign out"; clicking calls logout |

**Run:**
```bash
cd frontend && pnpm test && pnpm lint && pnpm typecheck && pnpm build
make test
```

**Manual verification:**
1. Signed out → `/login` shown. Sign in → shell with your email.
2. Click around sidebar rows and nav links → URL + highlight change.
3. Sign out → back to login.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
