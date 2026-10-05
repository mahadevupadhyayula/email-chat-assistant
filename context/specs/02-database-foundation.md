# Unit 02: Database foundation

## What to build
Async SQLAlchemy engine/session setup, Alembic migrations, the first three tables (`users`, `sessions`, `oauth_credentials`), a `get_db` dependency, pytest fixtures against the real test database, and `GET /api/health` reporting DB connectivity.

## Why
Auth (Unit 03) needs users, sessions and credentials tables; every later unit uses the session dependency and test fixtures created here.

## Scope
**In scope**
- `app/db/` (base, session, models for the three tables), Alembic config + first revision.
- `get_db` dependency; health check runs `SELECT 1`.
- Test fixtures: migrate test DB once per session, truncate tables between tests, `db_session`, `client`, `user_factory`.
- `make migrate` target.

**Out of scope (do not build in this unit)**
- Any service functions or endpoints for users/sessions (Unit 03). Other tables (06, 10, 12, 16).

## Prerequisites
- Unit 01 complete. `make db` running.

## How to build it

### `backend/app/db/base.py`
- `class Base(DeclarativeBase)` with `metadata = MetaData(naming_convention={"ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"})`.
- `class UUIDPkMixin`: `id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)`.
- `class TimestampMixin`: `created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())`, `updated_at` same + `onupdate=func.now()`.

### `backend/app/db/session.py`
- `def create_engine(url: str) -> AsyncEngine` (`pool_pre_ping=True`).
- `def create_session_factory(engine) -> async_sessionmaker[AsyncSession]` (`expire_on_commit=False`).
- Engine + factory created in `create_app` lifespan and stored on `app.state.engine` / `app.state.session_factory`; engine disposed on shutdown.

### `backend/app/db/models/`
- `__init__.py` imports all models (so Alembic autogenerate sees them) and re-exports `User`, `Session`, `OAuthCredential`.
- `user.py` — `User(Base, UUIDPkMixin, TimestampMixin)`, table `users`: `email: str` (String(320), unique, index), `name: str | None` (String(200)), `avatar_url: str | None` (Text).
- `session.py` — `Session` table `sessions`: `user_id` FK `users.id` ondelete CASCADE (index), `token_hash: str` (String(64), unique), `expires_at` (timestamptz), `created_at`.
- `oauth_credential.py` — `OAuthCredential` table `oauth_credentials`: `user_id` FK CASCADE, `provider: str` (String(20)), `encrypted_refresh_token: str` (Text), `encrypted_access_token: str | None` (Text), `access_token_expires_at: datetime | None`, `scopes: list[str]` (ARRAY(Text)), `status: str` (String(20), default `"active"`, CHECK in (`active`,`revoked`)), timestamps; `UniqueConstraint("user_id", "provider")`.

### Alembic
- `cd backend && uv run alembic init -t async alembic`.
- `alembic/env.py`: read URL from `get_settings().database_url` (allow override via `-x db_url=...` for tests), `target_metadata = Base.metadata`, `compare_type=True`.
- Generate `uv run alembic revision --autogenerate -m "users sessions oauth_credentials"`; hand-check the file.
- Makefile: `migrate: cd backend && uv run alembic upgrade head`.

### `backend/app/api/deps.py`
- `async def get_db(request: Request) -> AsyncIterator[AsyncSession]`: open from `request.app.state.session_factory`, `yield`, `commit()` on success, `rollback()` on exception.

### Health
- `app/services/health.py`: `async def check_database(session: AsyncSession) -> bool` — runs `SELECT 1`, returns False on `SQLAlchemyError`/`OSError`.
- `GET /api/health` → `{"status": "ok", "database": "ok"}` or `{"status": "degraded", "database": "unreachable"}` (HTTP 200 either way). Update `HealthResponse` to add `database: Literal["ok", "unreachable"]`.

### Tests — `backend/tests/conftest.py`
- Session-scoped fixture `migrated_db_url`: forces `APP_ENV=test`, runs Alembic `upgrade head` against `TEST_DATABASE_URL` programmatically (`alembic.command.upgrade(cfg, "head")` in a thread).
- Fixture `app`: `create_app(Settings(app_env="test", database_url=<test url>))` with lifespan run via `asgi-lifespan`-free approach: call `async with app.router.lifespan_context(app)`.
- Fixture `client`: `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`.
- Fixture `db_session`: session from `app.state.session_factory`.
- Autouse fixture `clean_tables`: after each test, `TRUNCATE` every table in `Base.metadata.sorted_tables` (reversed) `RESTART IDENTITY CASCADE`.
- Fixture `user_factory`: `async def make(email="me@example.com", name="Me") -> User` inserts and commits.

## Patterns, frameworks & concepts
- **Use:** SQLAlchemy 2.0 typed `Mapped[...]` / `mapped_column` declarative style.
- **Use:** one `AsyncSession` per request via dependency; services receive the session as their first argument.
- **Use:** real Postgres for integration tests (no SQLite) — ARRAY columns and LangGraph checkpointer need Postgres.
- **Avoid:** `Base.metadata.create_all` anywhere, including tests — schema comes only from Alembic.
- **References:** architecture.md → Data Model; code-standards.md → Testing.

## Design
N/A — no UI changes. (The Unit 01 placeholder page keeps showing `API: ok`.)

## Dependencies
- `sqlalchemy[asyncio]` — ORM; `asyncpg` — async driver; `alembic` — migrations.

## Success criteria
- [ ] `make migrate` creates `users`, `sessions`, `oauth_credentials`, `alembic_version` in `email_assistant`.
- [ ] `GET /api/health` returns `{"status":"ok","database":"ok"}` with Postgres up and `{"status":"degraded","database":"unreachable"}` with `docker compose stop db`.
- [ ] Tests run against `email_assistant_test` and leave it empty afterwards.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Integration | `tests/integration/test_health.py` | `test_health_reports_database_ok` | 200, `database == "ok"` |
| Integration | `tests/integration/test_health.py` | `test_health_degraded_when_db_unreachable` | app built with `database_url` pointing at port 1 → `status == "degraded"` |
| Integration | `tests/integration/test_models.py` | `test_user_email_unique` | inserting two users with same email raises `IntegrityError` |
| Integration | `tests/integration/test_models.py` | `test_credential_unique_per_provider` | two `google` credentials for one user → `IntegrityError` |
| Integration | `tests/integration/test_models.py` | `test_deleting_user_cascades` | deleting a user removes its sessions + credentials |
| Integration | `tests/integration/test_migrations.py` | `test_no_pending_model_changes` | Alembic `compare_metadata` between migrated DB and `Base.metadata` returns `[]` |

**Run:**
```bash
make test
make lint
```

**Manual verification:**
1. `make migrate` → `docker compose exec db psql -U app -d email_assistant -c '\dt'` shows the 3 tables.
2. `curl localhost:8000/api/health` → `database: ok`; stop db → `degraded`.

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
