# P0-S02 — Backend scaffold

## A. Task identification
| Field | Value |
|---|---|
| Phase | 0 Foundation |
| Step | 2 |
| Task ID | P0-S02 |
| Synverk card | TRAC-1 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | optional (Ruhan) |
| Priority | High |
| Effort | 1 day |
| Status | NEEDS REVIEW |
| Branch | `rafique/P0-S02-S05-backend-and-contracts` (batched with P0-S05) |

## B. Objective
Create the empty but running FastAPI backend that every backend feature folder plugs into: settings, DB session, health endpoint, Postgres, migrations, task runner, lint and tests. It is the root of the critical path (P0-S05, P1-S01, P1-S05 wait on it).

## C. Prerequisites
- P0-S01 (so the PR can be reviewed).
- Installed: `uv`, Docker Desktop, `task` (Taskfile CLI). Install task with `winget install Task.Task` if missing.
- Read: `docs/invariants/core.md`, `backend.md`, `tooling.md`, `security.md`.

## D. Technical background
- **Feature folders:** each feature is `backend/traceforge/<feature>/` with `router.py`, `schemas.py`, `models.py`, `repository.py`, `service.py` as needed. `main.py` only creates the app and includes routers.
- **Settings:** `pydantic-settings` `BaseSettings` with prefix `TRACEFORGE_`; nothing else reads env vars.
- **Compose credentials:** only `${VAR}` references; values in git-ignored `.env`. Healthcheck commands use `$${VAR}` so Compose doesn't substitute at parse time.
- **Alembic:** `env.py` builds the URL from `Settings`; models' `Base.metadata` is the autogenerate target.

## E. Implementation instructions
1. **Project:** `cd backend; uv init --package --name traceforge --python 3.12`. Dependencies: `uv add fastapi "uvicorn[standard]" pydantic-settings "sqlalchemy>=2" alembic "psycopg[binary]"`; dev: `uv add --dev pytest httpx ruff`.
2. **Layout:**
   ```
   backend/
     pyproject.toml, uv.lock, alembic.ini
     alembic/ (env.py, versions/)
     traceforge/
       __init__.py, main.py, config.py, database.py
       health/ __init__.py, router.py, schemas.py
     tests/ test_health.py
   ```
3. **`config.py`:** `Settings` with `db_host`, `db_port`, `db_name`, `db_user`, `db_password` (SecretStr), `env` (`dev`), computed `database_url`. `model_config = SettingsConfigDict(env_prefix="TRACEFORGE_", env_file="../.env")`. One cached `get_settings()`.
4. **`database.py`:** `create_engine(settings.database_url, pool_pre_ping=True)`, `SessionLocal`, `Base` (DeclarativeBase subclass), `get_db()` dependency.
5. **`health/`:** `HealthResponse(status: Literal["ok","degraded"], db: Literal["up","down"], version: str)`; router `GET /health` runs `SELECT 1` through the session inside try/except: DB failure → `status="degraded", db="down"` with HTTP 200 (the app itself is alive).
6. **`main.py`:** `app = FastAPI(title="TraceForge")`; `app.include_router(health_router)`. Nothing else.
7. **Root `compose.yaml`:** service `db` `postgres:16`, env `POSTGRES_USER: ${TRACEFORGE_DB_USER}` etc., healthcheck `pg_isready -U $${POSTGRES_USER}`, named volume, port `5432:5432`.
8. **`.env.example`** at root: every `TRACEFORGE_*` name with empty value and a one-line comment.
9. **Alembic:** `uv run alembic init alembic`; edit `env.py` to import `get_settings()` and `Base`; no hardcoded URL in `alembic.ini`.
10. **`Taskfile.yml`** (root, version 3): `dev` (compose up db + `uv run uvicorn traceforge.main:app --reload` in `backend/`), `test`, `lint` (`ruff check` + `ruff format --check`), `fmt`, `db:migrate` (`alembic upgrade head`), `db:revision` (with `NAME` var). Tasks must work from PowerShell.
11. **ruff config** in `pyproject.toml`: line length 100, rules `E,F,I,B,UP`.
12. **README:** setup (copy `.env.example`, fill values, `task dev`), commands table, how to test `/health` in `/docs`.

Edge cases: Postgres not ready when the API starts → health shows `down`, no crash; port 5432 already used on a laptop → document overriding the host port via `.env`.

## F. Checklist
- [x] uv project created with pinned Python 3.12 and lockfile
- [x] Dependencies and dev dependencies added
- [x] `config.py` with `Settings` and SecretStr password
- [x] `database.py` engine/session/Base/get_db
- [x] `health/` router + schema; DB-down handled
- [x] `main.py` only wires routers
- [x] `compose.yaml` Postgres with `${VAR}` and healthcheck
- [x] `.env.example` complete; `.env` git-ignored and not committed
- [x] Alembic initialised; URL from Settings
- [x] Taskfile: dev, test, lint, fmt, db:migrate, db:revision
- [x] ruff configured and clean
- [x] Tests written and passing (25 passed with Postgres up; health ok/degraded checked live)
- [x] README updated
- [x] No real credential values in tracked files (grep check)

## G. Expected deliverables
New: `backend/` (as above), `compose.yaml`, `.env.example`, `Taskfile.yml`. Modified: `README.md`. Endpoint: `GET /health`.

## H. Testing and validation
- `tests/test_health.py`: with DB up → `{"status":"ok","db":"up"}`; with the DB URL pointing to a closed port (override settings) → 200 `degraded`/`down`.
- Manual: `task dev`, open `http://localhost:8000/docs`, call `/health`; stop the db container, call again → `down`.
- `task lint` clean; `task test` green on both laptops.
- Acceptance: the commands above work from a fresh clone after only copying `.env.example` to `.env` and filling values.

## I. Dependencies and integration
- **Depends on:** P0-S01.
- **Unblocks:** P0-S05 (contracts package), P1-S01 (Taskfile), P1-S04 (DB/Alembic), P1-S05 (Settings), P0-S03 (health endpoint to call).
- **Integration:** every later backend feature registers its router in `main.py` through a small change in its own PR.

## J. Definition of done
Merged to `main`; health, lint and tests pass on both laptops; no credentials tracked; README explains setup; the user approved it in chat.
