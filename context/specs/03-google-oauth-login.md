# Unit 03: Google OAuth login & sessions

## What to build
Backend authentication: `GET /api/auth/google/login` → Google consent → `GET /api/auth/google/callback` creates/updates the user, stores Fernet-encrypted OAuth tokens, creates a server-side session and sets the `ea_session` cookie, then redirects to the frontend. Plus `GET /api/auth/me`, `POST /api/auth/logout`, the `get_current_user` dependency, a test-only `POST /api/auth/dev-login`, and the standard error-response shape.

## Why
Every user-owned feature needs an authenticated user, and Gmail access needs the stored credentials. Unit 04 builds the Login page on these endpoints; Unit 05 uses the credentials.

## Scope
**In scope**
- OAuth flow, state cookie, token encryption, sessions, current-user dependency, logout, me, dev-login (test/e2e only).
- Error handling scaffolding: `services/errors.py`, exception handlers, error JSON shape.
- README section: Google Cloud setup.

**Out of scope (do not build in this unit)**
- Any UI (Unit 04). Gmail API calls (Unit 05). Contacts backfill trigger (Unit 10). Token refresh (Unit 05).

## Prerequisites
- Unit 02 complete.
- For manual verification only: Google Cloud project, Gmail API enabled, OAuth client type "Web application", authorised redirect URI `http://localhost:8001/api/auth/google/callback`, consent screen in Testing with the user's Gmail as a test user.

## How to build it

### Env / settings
- Add to `.env.example` and `Settings`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI=http://localhost:8001/api/auth/google/callback`, `TOKEN_ENCRYPTION_KEY` (comment: generate with `uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`), `SESSION_SECRET` (random 32+ chars), `SESSION_TTL_DAYS=30`. In `test`/`e2e` env, defaults for these are allowed (fixed test values); in `development` they're required (validator raises a clear error if missing).
- `GOOGLE_SCOPES` constant in `app/security/oauth.py`: `["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.send"]`.

### `app/security/crypto.py`
- `class TokenCipher`: `__init__(key: str)`, `encrypt(plaintext: str) -> str`, `decrypt(ciphertext: str) -> str` (raises `TokenDecryptError` on `InvalidToken`).

### `app/security/sessions.py`
- `def new_session_token() -> str` (`secrets.token_urlsafe(32)`), `def hash_token(token: str) -> str` (sha256 hex).
- Cookie constants: `SESSION_COOKIE = "ea_session"`, `STATE_COOKIE = "ea_oauth_state"`.

### `app/security/oauth.py`
- `def build_flow(settings) -> google_auth_oauthlib.flow.Flow` from client config dict (no client_secret.json file).
- `def authorization_url(flow, state: str) -> str` with `access_type="offline"`, `prompt="consent"`, `include_granted_scopes="true"`.
- `async def exchange_code(settings, code: str) -> GoogleTokens` (run `flow.fetch_token` in a thread) where `GoogleTokens` dataclass = `access_token, refresh_token, expires_at, scopes, id_token_claims (email, name, picture)`. Verify the ID token with `google.oauth2.id_token.verify_oauth2_token`. Raise `OAuthExchangeError` if `refresh_token` is missing or `gmail.modify`/`gmail.send` not granted.
- State cookie: `itsdangerous.URLSafeTimedSerializer(SESSION_SECRET, salt="oauth-state")`; max age 600 s.

### `app/services/errors.py`
- `class DomainError(Exception)` with `code: str`, `status: int`, `message: str`. Subclasses: `UnauthenticatedError` (401 `unauthenticated`), `NotFoundError` (404 `not_found`), `ConflictError` (409 `conflict`), `OAuthExchangeError` (400 `oauth_failed`), `ProviderAuthError` (401 `provider_reauth_required`), `ProviderError` (502 `provider_error`).
- In `create_app`: handler for `DomainError` → `JSONResponse({"error": {"code", "message"}}, status)`; handler for `RequestValidationError` → 422 `validation_error`; generic `Exception` → 500 `internal_error` (logged with traceback, message "Something went wrong").

### `app/services/auth.py`
- `async def complete_google_login(db, cipher, tokens: GoogleTokens) -> tuple[User, str]`: upsert user by lowercase email (update name/avatar), upsert `oauth_credentials` (provider `google`, encrypted refresh + access tokens, expiry, scopes, status `active`), create session row with `hash_token(token)` and `expires_at = now + SESSION_TTL_DAYS`; return `(user, raw_token)`.
- `async def get_user_by_session_token(db, token: str) -> User` — joins sessions; raises `UnauthenticatedError` if missing/expired (deletes expired row).
- `async def logout(db, token: str) -> None` — deletes session row (no error if absent).
- `async def dev_login(db, email: str, name: str) -> tuple[User, str]` — upsert user, create session (no credentials).

### `app/schemas/auth.py`
- `MeResponse`: `id: UUID, email: EmailStr, name: str | None, avatar_url: str | None, gmail_status: Literal["active", "revoked", "missing"]`.
- `DevLoginRequest`: `email: EmailStr = "me@example.com"`, `name: str = "Test User"`.

### `app/api/auth.py` (`prefix="/api/auth"`)
- `GET /google/login` → create random state, set `STATE_COOKIE` (signed, httpOnly, SameSite=Lax, max_age 600), 302 to Google.
- `GET /google/callback?code&state` → verify state cookie matches + unexpired (else redirect `FRONTEND_URL/login?error=state`), exchange code, `complete_google_login`, set `SESSION_COOKIE` (httpOnly, SameSite=Lax, `secure=False`, path `/`, max_age TTL), delete state cookie, 302 to `FRONTEND_URL/`. On `OAuthExchangeError` or `?error=access_denied` → 302 `FRONTEND_URL/login?error=oauth`.
- `GET /me` → `MeResponse` (`gmail_status` from credentials row or `missing`).
- `POST /logout` → deletes session, clears cookie, 204.
- `app/api/dev_auth.py`: `POST /api/auth/dev-login` → sets cookie, returns `MeResponse`. Registered in `create_app` **only** if `settings.app_env in ("test", "e2e")`.

### `app/api/deps.py`
- `get_token_cipher(settings)`; `async def get_current_user(request, db) -> User`: reads `ea_session` cookie; raises `UnauthenticatedError` if missing.

### Test fixtures
- `auth_client` fixture: `client` after `POST /api/auth/dev-login`; `other_auth_client` for a second user (`other@example.com`) using a separate `AsyncClient`.

### README
- Add "Google Cloud setup" section with the prerequisite steps above and how to generate `TOKEN_ENCRYPTION_KEY` / `SESSION_SECRET`.

## Patterns, frameworks & concepts
- **Use:** server-side sessions — only `sha256(token)` stored; cookie carries the raw token.
- **Use:** signed short-lived state cookie for CSRF protection of the OAuth callback.
- **Use:** domain errors + central exception handlers (code-standards.md → API / Server Logic).
- **Avoid:** JWTs, storing tokens in the frontend, logging the callback query string (contains `code`).
- **References:** architecture.md → Auth and Access Model, Invariants 2, 6.

## Design
N/A — no UI changes (Unit 04 builds the Login page).

## Dependencies
- `google-auth`, `google-auth-oauthlib` — OAuth flow + ID token verification.
- `cryptography` — Fernet token encryption.
- `itsdangerous` — signed state cookie.

## Success criteria
- [ ] Visiting `http://localhost:8001/api/auth/google/login` goes to Google consent listing Gmail access; after consent the browser lands on `http://localhost:5173/` with an `ea_session` cookie.
- [ ] `oauth_credentials` row exists with encrypted (non-plaintext) tokens and `status = active`.
- [ ] `GET /api/auth/me` (via `localhost:5173/api/auth/me`) returns the user's email and `gmail_status: "active"`; without a cookie returns 401 `{"error":{"code":"unauthenticated",...}}`.
- [ ] `POST /api/auth/logout` makes `/me` return 401.
- [ ] `POST /api/auth/dev-login` returns 404 when `APP_ENV=development`.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Unit | `tests/unit/test_crypto.py` | `test_encrypt_roundtrip` | decrypt(encrypt(x)) == x and ciphertext != x |
| Unit | `tests/unit/test_crypto.py` | `test_decrypt_wrong_key_raises` | `TokenDecryptError` |
| Unit | `tests/unit/test_sessions.py` | `test_hash_token_is_sha256_hex` | 64 hex chars, deterministic |
| Integration | `tests/integration/test_auth.py` | `test_login_redirects_to_google_with_state_cookie` | 302, `Location` host `accounts.google.com`, includes `access_type=offline`, state cookie set |
| Integration | `tests/integration/test_auth.py` | `test_callback_rejects_bad_state` | 302 to `/login?error=state`, no session created |
| Integration | `tests/integration/test_auth.py` | `test_callback_creates_user_credentials_session` | monkeypatch `exchange_code` to return fake `GoogleTokens`; 302 to frontend; user + encrypted credential + session rows exist; cookie set |
| Integration | `tests/integration/test_auth.py` | `test_callback_missing_refresh_token_redirects_error` | `exchange_code` raises `OAuthExchangeError` → `/login?error=oauth` |
| Integration | `tests/integration/test_auth.py` | `test_me_requires_session` | 401 + error shape |
| Integration | `tests/integration/test_auth.py` | `test_me_returns_user` | via `auth_client`, email matches, `gmail_status == "missing"` |
| Integration | `tests/integration/test_auth.py` | `test_expired_session_is_rejected` | set `expires_at` in past → 401, row deleted |
| Integration | `tests/integration/test_auth.py` | `test_logout_invalidates_session` | after logout `/me` → 401 |
| Integration | `tests/integration/test_auth.py` | `test_dev_login_not_registered_in_development` | app with `app_env="development"` → 404 |

**Run:**
```bash
make test
make lint
```

**Manual verification:**
1. Fill Google vars in `.env`, restart backend.
2. Open `http://localhost:8001/api/auth/google/login`, consent → lands on `localhost:5173`.
3. Open `http://localhost:5173/api/auth/me` → JSON with your email, `gmail_status: "active"`.
4. `docker compose exec db psql -U app -d email_assistant -c 'select left(encrypted_refresh_token, 12) from oauth_credentials'` → Fernet ciphertext (starts with `gAAAA`).

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
