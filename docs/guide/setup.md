# Setup and run

Back to [TraceForge Explained](TraceForge-Explained.md). Every command below appears in `README.md` or `Taskfile.yml`. Platform: Windows, PowerShell. I did **not** execute them while writing this guide; the test results quoted in [testing](testing.md) come from `docs/orchestration/STATE.md`.

## 1. What you need installed
From the README: [uv](https://docs.astral.sh/uv/), [Task](https://taskfile.dev) (`winget install Task.Task`), Docker Desktop. For the frontend: Node LTS and pnpm (`corepack enable`, or `npm i -g pnpm` if that needs admin; see [problem log](problem-log.md)). For a local model: Ollama (`docs/invariants/tooling.md`).

## 2. First run (backend + database)

```powershell
git clone https://github.com/Rafique610/traceforge.git
cd traceforge
Copy-Item .env.example .env   # then fill in TRACEFORGE_DB_NAME, _USER, _PASSWORD
task dev                      # starts Postgres, then the API on http://localhost:8000
```

If port 5432 is taken, set `TRACEFORGE_DB_PORT` in `.env` (README suggests `5433`).

Check: open http://localhost:8000/docs, expand `GET /health`, click *Try it out*, *Execute*. Expected: `{"status":"ok","db":"up","version":"0.1.0"}`. After `task db:down` it shows `degraded` / `down` instead of crashing.

## 3. Task commands (from `Taskfile.yml`)

| Command | What it does |
|---|---|
| `task dev` | Start Postgres, then the API with auto-reload (runs in `backend/`) |
| `task db:up` / `task db:down` | Start / stop Postgres only (data kept in a named volume) |
| `task test` | Backend pytest (extra args allowed via `CLI_ARGS`); the DB-up health test is skipped if Postgres is not running |
| `task lint` | `ruff check .` and `ruff format --check .` |
| `task fmt` | Auto-fix lint and format |
| `task db:migrate` | Apply Alembic migrations (needs Postgres) |
| `task db:revision NAME=...` | Create a migration from model changes |
| `task contracts:schema` | Regenerate JSON Schema for the contracts |
| `task web` | Frontend dev server on http://localhost:5173 (proxies `/api` to :8000) |
| `task web:test` | Vitest, once |
| `task web:build` | Type-check and production build |
| `task llm:smoke PROVIDER=ollama` | One tool-call round trip and a cache check |
| `task agent:run CASE=all CONDITION=G0` | Run the pipeline agent on the sample cases (`CASE` defaults to `all`, `CONDITION` to `G0`) |

The last two tasks exist in `Taskfile.yml` but are not yet in the README's command table.

## 4. Frontend

```powershell
pnpm --dir frontend install
task dev        # API on :8000 (in one terminal)
task web        # UI on http://localhost:5173, /api is proxied to :8000
task web:test
task web:build
```

The header badge shows "API ok", "API degraded" (database down) or "API unreachable". `VITE_API_URL` overrides the API base.

## 5. Settings you may need

Names only; values go in the git-ignored `.env` (all from `.env.example` and `config.py`):

`TRACEFORGE_ENV`, `TRACEFORGE_DB_HOST`, `_DB_PORT`, `_DB_NAME`, `_DB_USER`, `_DB_PASSWORD`, `TRACEFORGE_LLM_PROVIDER` (`ollama | openrouter | mistral | groq`), `TRACEFORGE_LLM_MODEL`, `TRACEFORGE_LLM_FREE_ONLY`, `TRACEFORGE_OPENROUTER_API_KEY`, `_MISTRAL_API_KEY`, `_GROQ_API_KEY`.

Defaults in `config.py`: provider `ollama`, model `qwen2.5-coder:7b`, base URL `http://localhost:11434/v1`, free-only on, allowlist `ollama` and `openrouter`.

## 6. Incidents API check
`/docs` lists `POST /incidents`, `GET /incidents`, `GET /incidents/{id}`, `/events` and `/evidence`. Apply the migration with `task db:migrate` (needs `task db:up`). Note: the migration is documented in its own header as not yet applied on Postgres, so this step is **pending verification** (see [testing](testing.md)).

## 7. Machine notes recorded in the project (2026-11-21)
Decision B3 (`docs/orchestration/DECISIONS.md`): on the developer laptop the Ollama model store for future pulls is `D:\AI\Models\ollama` (user env `OLLAMA_MODELS`), `HF_HOME` is `D:\AI\Caches\huggingface` and `UV_CACHE_DIR` is `D:\AI\Caches\uv`, because `C:` was 91% full. These are machine settings, not project requirements.
