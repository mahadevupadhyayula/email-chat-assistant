# UI Context

## Theme
Dark only in v1. Visual language: **dark, technical, dense** — near-black zinc surfaces, thin 1px borders instead of shadows, compact 14px UI text, monospace for metadata (dates, addresses, counts, Gmail queries), and a single emerald accent used sparingly for primary actions, focus and "live" indicators. Think terminal-adjacent tools (Linear dark, Raycast): information-rich, no decoration.

`<html class="dark">` is set permanently; there is no theme toggle.

## Colour Tokens
All components use these tokens via Tailwind theme mapping (`@theme inline` in `globals.css`). No raw hex values in components. Tailwind names deliberately avoid shadcn's reserved names (`primary`, `secondary`, `muted`, `accent`, `border`): text colours are `fg-*`, the emerald accent is `brand-*`, borders are `line-*`.

| Role | Token | Dark value | Tailwind name |
| ---- | ----- | ---------- | ------------- |
| Page background | `--bg-base` | `#09090B` | `bg-base` |
| Surface (sidebar, cards) | `--bg-surface` | `#111113` | `bg-surface` |
| Elevated surface (popovers, dialogs, approval card) | `--bg-elevated` | `#18181B` | `bg-elevated` |
| Hover / selected row | `--bg-hover` | `#1F1F23` | `bg-hover` |
| Primary text | `--text-primary` | `#FAFAFA` | `text-fg` |
| Secondary text (message body) | `--text-secondary` | `#D4D4D8` | `text-fg-secondary` |
| Muted text (metadata, placeholders) | `--text-muted` | `#A1A1AA` | `text-fg-muted` |
| Disabled text | `--text-disabled` | `#52525B` | `text-fg-disabled` |
| Primary accent | `--accent-primary` | `#10B981` | `bg-brand` / `text-brand` |
| Accent hover | `--accent-hover` | `#34D399` | `bg-brand-hover` |
| Accent foreground (text on accent) | `--accent-foreground` | `#022C22` | `text-brand-foreground` |
| Accent subtle (tinted backgrounds, selected conversation) | `--accent-subtle` | `#052E22` | `bg-brand-subtle` |
| Border | `--border-default` | `#27272A` | `border-line` |
| Strong border (inputs, card focus) | `--border-strong` | `#3F3F46` | `border-line-strong` |
| Focus ring | `--ring` | `#34D399` | `ring` |
| Error | `--state-error` | `#F87171` | `text-error` / `border-error` |
| Error subtle background | `--state-error-subtle` | `#2A1215` | `bg-error-subtle` |
| Warning | `--state-warning` | `#FBBF24` | `text-warning` |
| Warning subtle background | `--state-warning-subtle` | `#2A2008` | `bg-warning-subtle` |
| Success | `--state-success` | `#4ADE80` | `text-success` |
| Info | `--state-info` | `#60A5FA` | `text-info` |
| Unread indicator | `--unread-dot` | `#10B981` | `bg-unread` |

shadcn's variables are aliased to these in `globals.css`: `--background: var(--bg-base)`, `--foreground: var(--text-primary)`, `--card: var(--bg-surface)`, `--popover: var(--bg-elevated)`, `--primary: var(--accent-primary)`, `--primary-foreground: var(--accent-foreground)`, `--secondary: var(--bg-hover)`, `--muted: var(--bg-hover)`, `--muted-foreground: var(--text-muted)`, `--accent: var(--bg-hover)`, `--destructive: var(--state-error)`, `--border: var(--border-default)`, `--input: var(--border-strong)`, `--ring: var(--ring)`.

Triage group colours (left border 2px on group header): Needs reply → `--state-error`, Important → `--state-warning`, FYI → `--state-info`, Low priority → `--text-disabled`.

## Typography
| Role | Font | Token | Sizes |
| ---- | ---- | ----- | ----- |
| UI + body | Inter Variable (`@fontsource-variable/inter`) | `--font-sans` | 14px/20px base (`text-sm`), 13px/18px secondary (`text-[13px]` via `text-meta` utility) |
| Headings | Inter Variable 600 | `--font-sans` | Page title 18px/24px (`text-lg font-semibold`); card title 14px 600 |
| Metadata / code / addresses / dates / Gmail queries | JetBrains Mono (`@fontsource/jetbrains-mono` 400) | `--font-mono` | 12px/16px (`text-xs font-mono`) |

No text larger than 18px anywhere in v1. Line length of assistant messages capped at 72ch (`max-w-[72ch]`).

## Spacing & Radius
| Context | Value / class |
| ------- | ------------- |
| Base spacing unit | 4px (Tailwind default) |
| Sidebar width | 260px fixed (`w-[260px]`), collapsible to 0 on < 1280px via toggle |
| Chat column | `max-w-3xl` (768px) centred, `px-4` |
| Message vertical gap | `gap-4` |
| Card padding | `p-3` (dense) |
| List row height | 32px (`h-8`) sidebar rows; 40px (`h-10`) table rows |
| Inputs / buttons height | 32px (`h-8`), composer min-height 44px |
| Radius small (inputs, badges) | 4px `rounded-sm` |
| Radius default (buttons, cards) | 6px `rounded-md` |
| Radius large (dialogs) | 8px `rounded-lg` |
| Borders | 1px `border-line`; no drop shadows except dialogs (`shadow-lg` with black 50%) |

## Component Library
- shadcn/ui (new-york style, CSS variables on, base colour zinc) — generated into `frontend/src/components/ui/`. Add with `pnpm dlx shadcn@latest add <name>`. Never edit generated files; wrap them in feature components.
- Planned primitives: `button`, `input`, `textarea`, `scroll-area`, `separator`, `tooltip`, `avatar`, `dropdown-menu`, `skeleton`, `dialog`, `alert-dialog`, `badge`, `table`, `checkbox`, `switch`, `select`, `toggle-group`, `label`, `sonner`.
- Buttons: `default` (emerald, for the one primary action per view: Send, Approve & send, Save digest), `secondary` (bg-hover), `ghost` (sidebar/icon buttons), `destructive` (Delete, Reject is `secondary` not destructive).

## Layout Patterns
- **Login (`/login`):** full-screen `bg-base`, centred 360px column: app name (18px semibold), one-line tagline (muted), "Sign in with Google" default button full width, footnote in mono muted: "Requests Gmail read, modify and send access."
- **App shell (all authenticated routes):** 2 columns. Left: Sidebar (260px, `bg-surface`, right border). Right: main area `bg-base`. Optional `ReconnectBanner` spans the top of the main area (warning subtle bg, 40px tall).
- **Sidebar (top → bottom):** header row (app name + collapse button), "New chat" button (secondary, full width, `Plus` icon, shortcut hint `⌘K` in mono muted), conversation list (scroll-area; rows 32px, title truncated, selected row `bg-brand-subtle` + 2px emerald left border, hover shows `MoreHorizontal` menu with Rename / Delete), separator, nav links (Contacts `Users`, Digests `CalendarClock`), footer: avatar + email (mono 12px truncated) + dropdown (Reconnect Gmail, Sign out).
- **Chat (`/c/:conversationId`, `/` redirects to newest or new):** header bar 48px (conversation title, editable on click). Message list (scroll-area, auto-scroll to bottom while streaming unless user scrolled up). User messages: right-aligned, `bg-elevated` bubble `rounded-md p-3 max-w-[80%]`. Assistant messages: left-aligned, no bubble, Markdown, cards rendered below text. Tool status row: 12px mono muted with spinner `Loader2` "searching mail · from:priya newer_than:30d". Composer pinned at bottom: textarea auto-grow (max 8 lines), Enter sends, Shift+Enter newline, send button (icon `ArrowUp`, emerald) disabled while streaming; a Stop button (`Square`) replaces it while streaming.
- **Email card:** `bg-surface border border-line rounded-md p-3`, 2 lines: row 1 sender name (14px primary) + address (mono muted) + date right-aligned (mono muted) + unread dot; row 2 subject (secondary) + snippet (muted, truncated 1 line). Lists of cards stack with `gap-2`; more than 5 → show 5 + "Show N more".
- **Approval card:** `bg-elevated border border-line-strong rounded-md`, header row with icon (`Send` / `Archive` / `Tag`) + title ("Approve reply", "Approve new email", "Approve archive (12 emails)"), body (fields or list), footer right-aligned: Reject (secondary) + Approve (default). After decision it collapses into a receipt row (success `CheckCircle2` "Sent to priya@… · 10:42" or muted `XCircle` "Rejected").
- **Contacts (`/contacts`):** page header (title, search input 240px, "Show automated" switch, Sync now (secondary, `RefreshCw`), Add contact (default)). Table: Name, Email (mono), Sent, Received, Last interaction (mono relative date), Source badge (`auto`/`manual`), row menu (Rename, Delete for manual). Sync status line under the header in mono muted ("Synced 4 min ago" / "Syncing…" / error in `text-error`).
- **Digests (`/digests`, `/digests/new`, `/digests/:id`):** list page = cards per digest (name, schedule summary in mono "Mon–Fri · 08:00 · Europe/London", focus first line, enabled switch, last run status badge). Form page = single column 640px: Name, Days (toggle-group of 7 day pills), Time (time input), Timezone (select, default browser timezone), Focus instructions (textarea), Filters (three tag inputs: senders, labels, keywords), Lookback hours (number), Enabled switch; footer Save / Cancel / Delete (edit only) / Send now (edit only). Below form on edit: Run history table (last 20 runs).
- **Breakpoints:** desktop-only; min supported width 1024px. Below 1280px the sidebar starts collapsed.

## States
- **Loading:** skeleton rows for lists (sidebar: 6 rows; contacts table: 8 rows; digests: 3 cards). Streaming assistant message shows a blinking 2px emerald caret. Buttons show `Loader2` spinner and are disabled during mutations. No full-page spinners except the initial `useMe` check (centred `Loader2`).
- **Empty:** centred in content area: lucide icon 24px muted, one-line title (primary), one-line hint (muted), optional primary button. Chat empty state shows 4 suggested-prompt buttons (secondary, 2×2 grid) that send on click.
- **Error:** inline, never modal. Error row: `bg-error-subtle border border-error/40 rounded-md p-3`, `AlertCircle` icon, message, optional Retry button. Form field errors under the field in 12px `text-error`. Reauth → global `ReconnectBanner`. Success confirmations → `sonner` toast bottom-right, 3 s.

## Icons
lucide-react only. Sizes: 16px default (`size-4`), 14px inline with 12px text (`size-3.5`), 24px empty states (`size-6`). Stroke width 1.75. Icons inherit `currentColor`; icon-only buttons need `aria-label` and a tooltip.

## Accessibility
- WCAG AA contrast for all text against its background (tokens above satisfy this; `--text-disabled` only for disabled controls).
- Every interactive element keyboard reachable; visible focus ring `ring-2 ring-ring ring-offset-2 ring-offset-base`.
- Keyboard shortcuts: Enter send, Shift+Enter newline, `⌘K`/`Ctrl+K` new chat, `Esc` stops streaming.
- Streaming message container has `aria-live="polite"`; approval card buttons have explicit labels ("Approve and send email to priya@example.com").
- Icon-only buttons have `aria-label`. Form inputs have associated `<Label>`.
