# TraceForge

*Trace the failure. Forge the fix.*

TraceForge diagnoses reproducible failures in Dockerized Python services, links runtime evidence (logs, health, effective config, tracebacks) to the exact source code and configuration keys, proposes a minimal code or config patch, and checks it against independent tests in an isolated sandbox. Every patch goes to an engineer for approve/reject review; nothing is deployed automatically.

AI-4009 Generative AI semester project (FAST-NUCES), R&D Product track.

## Status

The pipeline runs end to end on the lab cases: incidents API with an audited state machine, model gateway, pipeline agent, repair loop with sandbox verification, evidence report with hash-bound review, GitHub intake and the reviewer UI, on top of the victim lab, Docker sandbox, fault generator (4 validated development cases), evidence collector, code graph, retrieval and metrics. Still open: the frozen evaluation dataset and the full 2x2 experiments. Progress and ownership: [`docs/plans/TEAM_WORK_DISTRIBUTION.md`](docs/plans/TEAM_WORK_DISTRIBUTION.md). Explanation for newcomers: [`docs/guide/TraceForge-Explained.md`](docs/guide/TraceForge-Explained.md). The plan is in [`docs/plans/README.md`](docs/plans/README.md).

## Setup (Windows, PowerShell)

Needs: [uv](https://docs.astral.sh/uv/), [Task](https://taskfile.dev) (`winget install Task.Task`), Docker Desktop.

```powershell
git clone https://github.com/Rafique610/traceforge.git
cd traceforge
Copy-Item .env.example .env   # then fill in TRACEFORGE_DB_NAME, _USER, _PASSWORD
task dev                      # starts Postgres, then the API on http://localhost:8000
```

If port 5432 is already taken on your laptop, set `TRACEFORGE_DB_PORT` in `.env` to another port (e.g. `5433`).

Check it works: open http://localhost:8000/docs, expand `GET /health`, click *Try it out* → *Execute*. You should see `{"status":"ok","db":"up","version":"0.1.0"}`. Stop the database (`task db:down`) and run it again: it shows `"degraded"` / `"down"` instead of crashing.

## Commands

| Command | What it does |
|---|---|
| `task dev` | Start Postgres, then the API with auto-reload |
| `task db:up` / `task db:down` | Start / stop Postgres only (data is kept) |
| `task test` | Run backend tests (the DB-up health test is skipped if Postgres isn't running) |
| `task lint` | ruff lint + format check |
| `task fmt` | Auto-fix lint and format |
| `task db:migrate` | Apply Alembic migrations |
| `task db:revision NAME=...` | Create a migration from model changes |
| `task contracts:schema` | Regenerate JSON Schema for the contracts |
| `task spike:retrieval` | Rerun the P0-S06 retrieval spike (needs ripgrep: `winget install BurntSushi.ripgrep.MSVC`); results in `docs/research/limits-report.md` |
| `task llm:smoke PROVIDER=ollama` | One tool-call round trip through the gateway, then a cache-hit check |
| `task agent:run CASE=all CONDITION=G0` | Run the pipeline agent on the sample cases (needs a model; see `.env.example`) |

## Frontend

Vite + React + TypeScript in `frontend/` (pnpm). Needs Node LTS and pnpm (`corepack enable`, or `npm i -g pnpm` if that needs admin).

```powershell
pnpm --dir frontend install
task dev        # API on :8000 (in one terminal)
task web        # UI on http://localhost:5173, /api is proxied to :8000
task web:test   # Vitest
task web:build  # type check + production build
```

The header badge shows "API ok", "API degraded" (database down) or "API unreachable", straight from `/health`. `VITE_API_URL` overrides the API base.

## Incidents API

`/docs` lists `POST /incidents`, `GET /incidents`, `GET /incidents/{id}`, `/events` and `/evidence`. Incident states are guarded; an illegal move returns 409. Apply the migration with `task db:migrate` (needs Postgres: `task db:up`).

## Layout

```
backend/traceforge/     one folder per feature (health/, contracts/, ...); main.py only wires routers
backend/tests/          pytest
backend/alembic/        migrations (URL comes from Settings, never from alembic.ini)
compose.yaml            Postgres for the app
docs/                   rules, project facts, the execution plan
```

## Shared contracts

`backend/traceforge/contracts/` holds the five data shapes the two tracks exchange: `CaseManifest`, `EvidenceBundle`, `ContextBundle`, `TestRunRequest`/`TestRunResult`, `AgentRunRecord`. `contracts/samples/` has three realistic samples per contract (a distance-1 config case, a code case, an abstain case), so each side can build against them before the real producer exists. JSON Schema is in `contracts/schema/`.

### Changing a contract
- A contract change is its own small PR that touches only `contracts/` (and its samples and schema), merged before any work that needs it.
- Within a phase, changes are additive only (new optional fields). Renames and removals wait for a phase boundary.
- Update the samples and run `task contracts:schema` and `task test` in the same PR; tell the other member the same day.
- Paths inside contracts are repo-relative POSIX strings (`lab/worker/queue.py`), never absolute or Windows paths.
