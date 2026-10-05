# Unit 05: Email provider layer

## What to build
The provider-neutral `EmailProvider` protocol and mail dataclasses, a `GmailProvider` implementing read operations (`search`, `get_thread`, `get_profile`) with token refresh and revocation handling, an in-memory `FakeEmailProvider`, a `get_email_provider` dependency, and two authenticated diagnostic endpoints: `GET /api/mail/search?q=&limit=` and `GET /api/mail/threads/{thread_id}`.

## Why
Every agent tool, the contacts sync and the digest worker talk to mail through this interface. The diagnostic endpoints let the user verify real Gmail access before the agent exists.

## Scope
**In scope**
- Read methods only: `get_profile`, `search`, `get_thread`.
- Credential loading/decryption/refresh/persisting, `revoked` detection → `ProviderAuthError`.
- HTML→text body extraction, truncation (Invariant 10).
- `FakeEmailProvider` with seeded fixture messages.

**Out of scope (do not build in this unit)**
- `send_message` (Unit 12), `archive`/`list_labels`/`create_label`/`apply_label` (Unit 15), header-metadata listing for contacts (Unit 10). Do not add stubs for them.

## Prerequisites
- Unit 03 complete; a real Google login done for manual checks.

## How to build it

### `app/email/types.py` (frozen, slotted dataclasses)
- `EmailAddress(name: str | None, email: str)`
- `EmailSummary(id: str, thread_id: str, from_: EmailAddress, to: list[EmailAddress], subject: str, snippet: str, date: datetime, labels: list[str], unread: bool)`
- `EmailMessage(EmailSummary fields + cc: list[EmailAddress], body_text: str, message_id_header: str | None, references_header: str | None)`
- `EmailThread(id: str, subject: str, messages: list[EmailMessage])`
- `MailProfile(email: str, messages_total: int)`

### `app/email/provider.py`
```python
class EmailProvider(Protocol):
    async def get_profile(self) -> MailProfile: ...
    async def search(self, query: str, limit: int = 10) -> list[EmailSummary]: ...
    async def get_thread(self, thread_id: str) -> EmailThread: ...
```
- `MAX_BODY_CHARS = 8000`, `MAX_RESULT_CHARS = 30000` constants live here.

### `app/email/gmail/`
- `client.py`: `def build_gmail_service(creds: google.oauth2.credentials.Credentials)` → `googleapiclient.discovery.build("gmail", "v1", credentials=creds, cache_discovery=False)`.
- `parsing.py`: pure functions — `parse_address_list(header: str) -> list[EmailAddress]` (`email.utils.getaddresses`, lowercase emails), `extract_body_text(payload: dict) -> str` (prefer `text/plain` part; else `text/html` via `html2text` with links ignored; base64url decode; strip quoted reply blocks starting with lines matching `^On .+ wrote:$`; truncate to `MAX_BODY_CHARS` with suffix `\n[…truncated]`), `to_summary(msg: dict) -> EmailSummary`, `to_message(msg: dict) -> EmailMessage`. Headers looked up case-insensitively. `date` from `internalDate` (ms epoch, UTC). `unread = "UNREAD" in labelIds`.
- `provider.py`: `class GmailProvider(EmailProvider)`; `__init__(self, creds: Credentials, on_refresh: Callable[[Credentials], Awaitable[None]])`. Every SDK call runs via `anyio.to_thread.run_sync`. Before each call, if `creds.expired`, refresh (`google.auth.transport.requests.Request()`) in thread and await `on_refresh(creds)`. Map errors: `google.auth.exceptions.RefreshError` or `HttpError` 401 → `ProviderAuthError`; `HttpError` 404 → `NotFoundError("Thread not found")`; other `HttpError`/`OSError` → `ProviderError`.
  - `search`: `users().messages().list(userId="me", q=query, maxResults=min(limit, 50))`, then `messages().get(format="metadata", metadataHeaders=["From","To","Subject","Date"])` for each id using one `BatchHttpRequest`; preserve list order.
  - `get_thread`: `users().threads().get(userId="me", id=thread_id, format="full")` → `EmailThread`; total body text across messages capped at `MAX_RESULT_CHARS` (oldest messages truncated first).
  - `get_profile`: `users().getProfile(userId="me")`.

### `app/email/fake.py`
- `class FakeEmailProvider(EmailProvider)`: `__init__(self, messages: list[EmailMessage] | None = None, owner_email: str = "me@example.com")`; defaults to `seed_messages()` — 12 deterministic messages across 6 threads (senders `priya@acme.com` contract thread, `sam@client.io` meeting thread, `billing@saas.com` invoice, 2 newsletters `news@digest.example` with label `CATEGORY_PROMOTIONS`, one sent-by-owner message with label `SENT`). Dates relative to a fixed `FAKE_NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)`.
  - `search` supports a minimal query subset: free-text terms (case-insensitive match in subject/snippet/body/from), `from:x`, `to:x`, `subject:x`, `is:unread`, `label:x`, `in:sent`, `after:<epoch>`; other operators ignored. Results newest first.
  - `get_thread` raises `NotFoundError` for unknown ids.
  - `fail_with: Exception | None` attribute — when set, every method raises it (for error-path tests).

### `app/services/credentials.py`
- `async def load_google_credentials(db, cipher, settings, user_id) -> Credentials` — loads row; raises `ProviderAuthError` if missing or `status == "revoked"`; builds `Credentials(token, refresh_token, token_uri, client_id, client_secret, scopes, expiry)` (expiry naive-UTC as google-auth expects).
- `async def persist_refreshed(db_factory, cipher, user_id, creds)` — encrypts and stores new access token + expiry in its own session/commit.
- `async def mark_revoked(db_factory, user_id)`.

### `app/api/deps.py`
- `async def get_email_provider(request, user, db, settings) -> EmailProvider`: if `settings.app_env in ("test","e2e")` return `request.app.state.fake_email_provider` (created in `create_app` for those envs); else build `GmailProvider` from `load_google_credentials` with `on_refresh` bound to `persist_refreshed`. When `GmailProvider` raises `ProviderAuthError`, `mark_revoked` is called before re-raising (wrap in provider via callback `on_auth_error`).

### `app/schemas/mail.py` + `app/api/mail.py` (`prefix="/api/mail"`)
- `EmailAddressOut`, `EmailSummaryOut`, `EmailMessageOut`, `EmailThreadOut` (Pydantic mirrors; `from_` serialised as `from`).
- `GET /search?q=<str 1..500>&limit=<1..25, default 10>` → `{"items": [EmailSummaryOut]}` via `services/mail.py:search_mail(provider, q, limit)`.
- `GET /threads/{thread_id}` → `EmailThreadOut` via `services/mail.py:get_thread(provider, thread_id)`.
- Comment at top of router: "Diagnostic + future UI read endpoints; the agent uses the provider directly via tools."

## Patterns, frameworks & concepts
- **Use:** Protocol-based port/adapter — `EmailProvider` is the port; Gmail and Fake are adapters (architecture.md → System Boundaries, Invariant 5).
- **Use:** run blocking SDK calls in threads (`anyio.to_thread.run_sync`), batch metadata fetches.
- **Use:** pure parsing functions tested against recorded Gmail JSON fixtures in `tests/fixtures/gmail/*.json` (hand-written, realistic, no real personal data).
- **Avoid:** importing `googleapiclient` outside `app/email/gmail/`; returning raw Gmail dicts past the provider; logging bodies or tokens.

## Design
N/A — no UI changes.

## Dependencies
- `google-api-python-client` — Gmail API.
- `html2text` — HTML bodies → text for the LLM.

## Success criteria
- [ ] Signed in, `localhost:5173/api/mail/search?q=newer_than:7d&limit=5` returns your 5 latest emails as JSON summaries.
- [ ] `localhost:5173/api/mail/threads/<thread_id from above>` returns the thread with readable `body_text`.
- [ ] After revoking app access at myaccount.google.com → Security → Third-party access, the search endpoint returns 401 `provider_reauth_required` and the credentials row becomes `revoked`; `/api/auth/me` reports `gmail_status: "revoked"`.
- [ ] Signing in again restores `active`.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `tests/unit/email/test_parsing.py` | `test_parse_address_list_handles_names_and_case` | `"Priya K <Priya@Acme.com>, b@x.io"` → 2 addresses, lowercased emails, name kept |
| Unit | same | `test_extract_body_prefers_plain_text` | multipart fixture → plain text part returned |
| Unit | same | `test_extract_body_converts_html` | html-only fixture → text without tags |
| Unit | same | `test_extract_body_truncates` | 20k-char body → length ≤ 8000 + suffix |
| Unit | same | `test_to_summary_maps_unread_and_date` | `UNREAD` label → `unread True`; `internalDate` → UTC datetime |
| Unit | `tests/unit/email/test_fake_provider.py` | `test_search_from_operator` | `from:priya@acme.com` returns only Priya's messages, newest first |
| Unit | same | `test_get_thread_unknown_raises` | `NotFoundError` |
| Unit | `tests/unit/email/test_gmail_provider.py` | `test_refresh_error_maps_to_provider_auth_error` | mocked service raising `RefreshError` → `ProviderAuthError`, `on_auth_error` awaited |
| Integration | `tests/integration/test_mail_api.py` | `test_search_requires_auth` | 401 |
| Integration | same | `test_search_returns_fake_results` | `auth_client` + `q=invoice` → 1 item from `billing@saas.com` |
| Integration | same | `test_thread_not_found` | 404 `not_found` |
| Integration | same | `test_provider_auth_error_maps_to_401` | fake `fail_with=ProviderAuthError()` → 401 `provider_reauth_required` |
| Integration | `tests/integration/test_credentials.py` | `test_load_credentials_missing_raises` | user with no row → `ProviderAuthError` |

**Run:**
```bash
make test
make lint
```

**Manual verification:**
1. Sign in, open the two diagnostic URLs above → real data.
2. Revoke access in Google account → search returns `provider_reauth_required`.
3. Sign in again via `/login` → works again.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
