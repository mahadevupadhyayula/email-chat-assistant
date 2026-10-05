# Unit 01: Project scaffold

## What to build
A runnable monorepo with `backend/` (FastAPI, uv) and `frontend/` (Vite React TS, pnpm), Docker Compose Postgres, a root Makefile, `.env.example`, lint/format/typecheck/test tooling on both sides, `GET /api/health` returning `{"status": "ok"}`, and a frontend page that displays the health status through the Vite proxy.

## Why
Every later unit assumes these commands, folders and tools exist. It proves the backend, frontend and proxy work together before any product code.

## Scope
**In scope**
- Folder structure from architecture.md (create only folders needed now + `.gitkeep` where listed below).
- Backend app factory, settings, health router, pytest smoke test.
- Frontend Vite app with Tailwind v4, a single placeholder page calling `/api/health`, Vitest smoke test.
- Docker Compose Postgres 16 with dev + test databases (not yet used by the app).
- Makefile, `.env.example`, `.gitignore`, `README.md`, `git init` with `main` branch.

**Out of scope (do not build in this unit)**
- Any DB connection code (Unit 02), auth (03), shadcn/theme tokens/router (04), LangChain (07).

## Prerequisites
- Installed locally: Python 3.12, `uv`, Node 22 LTS, `pnpm` 9+, Docker Desktop.

## How to build it

### Repo root
- `git init -b main`.
- `.gitignore`: `.env`, `.venv/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `node_modules/`, `dist/`, `frontend/test-results/`, `frontend/playwright-report/`, `.DS_Store`.
- `docker-compose.yml`: service `db` image `postgres:16`, env `POSTGRES_USER=app`, `POSTGRES_PASSWORD=app`, `POSTGRES_DB=email_assistant`, port `5432:5432`, volume `pgdata:/var/lib/postgresql/data`, mount `./docker/postgres-init.sql:/docker-entrypoint-initdb.d/init.sql:ro`, healthcheck `pg_isready -U app`.
- `docker/postgres-init.sql`: `CREATE DATABASE email_assistant_test OWNER app;`
- `.env.example` (each line with a comment):
  ```
  APP_ENV=development            # development | test | e2e
  LOG_LEVEL=INFO
  FRONTEND_URL=http://localhost:5173
  DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/email_assistant
  TEST_DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/email_assistant_test
  ```
  (Later units append their variables.)
- `Makefile` targets (all `.PHONY`):
  - `install`: `cd backend && uv sync` ; `cd frontend && pnpm install`
  - `dev-backend`: `cd backend && uv run uvicorn app.main:app --reload --port 8001 --env-file ../.env`
  - `dev-frontend`: `cd frontend && pnpm dev`
  - `db`: `docker compose up -d db`
  - `test`: `cd backend && uv run pytest` ; `cd frontend && pnpm test`
  - `lint`: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests` ; `cd frontend && pnpm lint && pnpm typecheck`
  - `format`: `cd backend && uv run ruff format . && uv run ruff check --fix .` ; `cd frontend && pnpm format`
  - `build`: `cd frontend && pnpm build`
- `README.md`: prerequisites, `cp .env.example .env`, `make db`, `make install`, `make dev-backend` + `make dev-frontend` in two terminals, open `http://localhost:5173`, `make test`, `make lint`. Link to `CLAUDE.md` and `context/`.

### Backend init
- `cd backend && uv init --app --python 3.12 --name email-assistant-backend` then delete the generated `main.py`/`hello.py`.
- `uv add fastapi "uvicorn[standard]" pydantic-settings`
- `uv add --dev pytest pytest-asyncio httpx ruff mypy`
- `pyproject.toml` additions:
  - `[tool.ruff] line-length = 100, target-version = "py312"`; `[tool.ruff.lint] select = ["E","F","W","I","B","UP","SIM","RUF","ASYNC","S"]`, `ignore = ["S101"]` under `[tool.ruff.lint.per-file-ignores] "tests/**" = ["S101","S105","S106"]`.
  - `[tool.mypy] strict = true, python_version = "3.12", plugins = ["pydantic.mypy"]`.
  - `[tool.pytest.ini_options] asyncio_mode = "auto", testpaths = ["tests"], asyncio_default_fixture_loop_scope = "session"`.
- Folders: `app/__init__.py`, `app/api/__init__.py`, `app/schemas/__init__.py`, `app/services/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`.
- `app/config.py`:
  ```python
  class Settings(BaseSettings):
      model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
      app_env: Literal["development", "test", "e2e"] = "development"
      log_level: str = "INFO"
      frontend_url: str = "http://localhost:5173"
      database_url: str = "postgresql+asyncpg://app:app@localhost:5432/email_assistant"
      test_database_url: str = "postgresql+asyncpg://app:app@localhost:5432/email_assistant_test"

  @lru_cache
  def get_settings() -> Settings: ...
  ```
- `app/schemas/health.py`: `class HealthResponse(BaseModel): status: Literal["ok", "degraded"]`.
- `app/api/health.py`: `router = APIRouter(prefix="/api", tags=["health"])`; `GET /api/health` → `HealthResponse(status="ok")`.
- `app/main.py`: `create_app(settings: Settings | None = None) -> FastAPI` — sets title "Email Assistant Chat API", configures `logging.basicConfig(level=settings.log_level)`, includes health router, stores settings on `app.state.settings`. Module-level `app = create_app()`.

### Frontend init
- `pnpm create vite@latest frontend --template react-ts`, then `cd frontend && pnpm install`.
- Remove boilerplate: `src/App.css`, `src/assets/react.svg`, `public/vite.svg`, demo counter code.
- `pnpm add -D tailwindcss @tailwindcss/vite vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event prettier eslint-config-prettier`.
- `vite.config.ts`: plugins `react()`, `tailwindcss()`; `resolve.alias` `@` → `./src`; `server.port = 5173`, `server.proxy = { "/api": { target: "http://localhost:8001", changeOrigin: false } }`; `test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], globals: true }` (use `/// <reference types="vitest/config" />`).
- `tsconfig.app.json`: `strict: true`, `noUncheckedIndexedAccess: true`, `baseUrl: "."`, `paths: {"@/*": ["src/*"]}`, `types: ["vitest/globals", "@testing-library/jest-dom"]`.
- `src/test/setup.ts`: `import "@testing-library/jest-dom/vitest";`
- `src/index.css` → rename to `src/styles/globals.css` containing `@import "tailwindcss";` only (tokens come in Unit 04).
- `src/App.tsx`: renders `<main>` with heading "Email Assistant Chat" and a status line: fetches `/api/health` in `useEffect` and shows `API: ok` / `API: unreachable`. (Temporary — replaced in Unit 04; this is the only allowed `fetch` outside `lib/` and is removed then.)
- `package.json` scripts: `dev: vite`, `build: tsc -b && vite build`, `preview: vite preview`, `test: vitest run`, `test:watch: vitest`, `lint: eslint .`, `typecheck: tsc -b --noEmit`, `format: prettier --write src`.
- `.prettierrc`: `{ "semi": true, "singleQuote": false, "printWidth": 100 }`. Add `eslint-config-prettier` to the flat config.

## Patterns, frameworks & concepts
- **Use:** FastAPI app factory pattern (`create_app`) so tests can build apps with custom settings.
- **Use:** `pydantic-settings` + `lru_cache` for a single settings object.
- **Use:** Vite dev proxy so the browser only ever talks to `localhost:5173` (same-origin cookies in Unit 03).
- **Avoid:** CORS middleware — not needed thanks to the proxy.
- **References:** architecture.md → Folder Structure; code-standards.md → Language & Types, Testing.

## Design
Placeholder only: unstyled heading + status text. Theme arrives in Unit 04.

## Dependencies
- Backend: `fastapi`, `uvicorn[standard]`, `pydantic-settings`; dev `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`.
- Frontend: Vite React TS template deps; dev `tailwindcss`, `@tailwindcss/vite`, `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `prettier`, `eslint-config-prettier`.

## Success criteria
- [ ] `make db` starts Postgres; `docker compose exec db psql -U app -l` lists `email_assistant` and `email_assistant_test`.
- [ ] `make dev-backend` → `curl localhost:8001/api/health` returns `{"status":"ok"}`.
- [ ] `make dev-frontend` → `http://localhost:5173` shows "Email Assistant Chat" and "API: ok"; with the backend stopped it shows "API: unreachable".
- [ ] `make test`, `make lint`, `make build` all pass.

## Required tests

**Automated — write these:**
| Type | File | Test | Asserts |
| ---- | ---- | ---- | ------- |
| Integration | `backend/tests/integration/test_health.py` | `test_health_returns_ok` | `GET /api/health` via `httpx.AsyncClient(transport=ASGITransport(create_app()))` → 200, body `{"status": "ok"}` |
| Unit | `backend/tests/unit/test_config.py` | `test_settings_defaults` | `Settings()` with no env has `app_env == "development"` and a `postgresql+asyncpg://` database_url |
| Unit | `frontend/src/App.test.tsx` | `renders app name` | heading "Email Assistant Chat" present (mock `fetch` with `vi.stubGlobal`) |
| Unit | `frontend/src/App.test.tsx` | `shows unreachable when health fails` | with fetch rejecting, "API: unreachable" appears |

**Run:**
```bash
make test
make lint
make build
```

**Manual verification:**
1. `cp .env.example .env && make db && make install`.
2. Run `make dev-backend` and `make dev-frontend` → browser shows "API: ok".
3. Stop the backend, reload → "API: unreachable".

## Definition of done
- [ ] All success criteria met
- [ ] Required tests written and passing; full test suite passing
- [ ] Lint, typecheck and build pass with no new warnings
- [ ] No invariant in architecture.md violated
- [ ] Only in-scope files changed
- [ ] progress-tracker.md updated
