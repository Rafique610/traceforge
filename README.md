# TraceForge

*Trace the failure. Forge the fix.*

TraceForge diagnoses reproducible failures in Dockerized Python services, links runtime evidence (logs, health, effective config, tracebacks) to the exact source code and configuration keys, proposes a minimal code or config patch, and checks it against independent tests in an isolated sandbox. Every patch goes to an engineer for approve/reject review; nothing is deployed automatically.

AI-4009 Generative AI semester project (FAST-NUCES), R&D Product track.

## Status

Release candidate RC1 (pipeline v5) is implemented and a staged, **reduced** final evaluation has been run on a seeded subset of the frozen test split: 35 variant groups at replicate 0, 12 at replicate 1, 8 at replicate 2 (stage 1 had 12 groups, stage 2 added 23); not the full 151-case protocol and not the A3 protocol (L0 vs G0 on at least 50 cases). No claim that the graph arm or feedback is better is established. Results, deviations and limitations: [`docs/research/final-evaluation-report.md`](docs/research/final-evaluation-report.md) (section 10 lists limitations). Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Two-key provider operations: [`docs/research/dual-key-operations.md`](docs/research/dual-key-operations.md). Chronology: [`docs/DEV_LOG.md`](docs/DEV_LOG.md). Plans: [`docs/plans/README.md`](docs/plans/README.md); newcomer guide: [`docs/guide/TraceForge-Explained.md`](docs/guide/TraceForge-Explained.md).

## Evaluation pipeline v5 (RC1) in brief

1. Dataset: generated fault cases with a frozen, hash-verified split (`datasets/manifests/test.json` + `test.sha256`).
2. Symptom: derived from the visible tests run on the base commit (no gold terms), redacted.
3. Evidence: logs, health, effective config, tracebacks, labelled by scope/basis/origin; deterministic diagnostics findings added.
4. Retrieval: lexical (L) or code-graph (G, with symptom-derived anchors), packed into a token-budgeted context.
5. Diagnosis: model plus local read-only tools; claims and targets are validated.
6. Patch: scoped edit proposal, up to 3 attempts; visible-test feedback (with provenance) on attempts 2-3 only in the `1` conditions.
7. Verification: the hidden suite runs once in a Docker sandbox on the frozen final patch and is never shown to a model.
8. Conditions: L0, G0, L1, G1 (retrieval arm x feedback).
9. Review: hash-bound evidence report, approve/reject by an engineer; nothing is auto-deployed.
10. Guards: leak guard, code-fingerprint gate, token ledger and 30 s pacing for the AxForge provider.

## Running the final evaluation

One replicate stage per invocation, from the repo root: `bash scripts/final_eval.sh K [CASES_FILE]` (K = replicate index; order L0, G0, then L1/G1 from the shared diagnosis; halts at the first failure, never retries). Two-key job scheduling: `python scripts/parallel_eval.py --jobs jobs.json` (see `docs/research/dual-key-operations.md`). These make real provider requests and spend a limited token allowance: run only with the owner's approval. Usage report (from `backend/`): `python -m traceforge.evaluation.usage_report`.

## Tests and Docker

- Backend: `task test` (or `cd backend; .venv/Scripts/python.exe -m pytest`); lint with `task lint`.
- Frontend: `task web:test`, `task web:build`.
- Docker: `docker compose up -d --wait db` starts Postgres for development (`compose.yaml`); `compose.prod.yaml` runs db + api + web (the API container runs `alembic upgrade head` on start).

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

Vite + React + TypeScript in `frontend/` (pnpm; CI uses `pnpm-lock.yaml`). Needs Node LTS and pnpm (`corepack enable`, or `npm i -g pnpm` if that needs admin). A machine with only npm can run the same scripts, but the lockfile is pnpm's.

```powershell
pnpm --dir frontend install
task dev        # API on :8000 (in one terminal)
task web        # UI on http://localhost:5173, /api is proxied to :8000
task web:test   # Vitest
task web:build  # type check + production build
```

The header badge shows "API ok", "API degraded" (database down) or "API unreachable", straight from `/health`. `VITE_API_URL` overrides the API base.

## Incidents API and the Investigate flow

`/docs` lists `POST /incidents`, `GET /incidents`, `GET /incidents/{id}`, `/events` and `/evidence`. Incident states are guarded; an illegal move returns 409. Apply the migration with `task db:migrate` (needs Postgres: `task db:up`).

**Investigate (added 2026-11-25).** `POST /incidents/{id}/investigate` starts a background investigation (diagnosis, repair loop, report) and returns 202; the reviewer UI's **Investigate** button calls it and polls the incident until its state changes. Responses: 404 unknown incident, 409 incident not in a startable state, 422 case not in the manifest, 503 when it cannot run. To use it:

1. Set `TRACEFORGE_MANIFEST` in `.env` to the case manifest (for example `datasets/manifests/dev.json`) and set a model provider key and provider (see `.env.example`; AxForge uses `TRACEFORGE_AXFORGE_API_KEY`). Never commit `.env`.
2. Start Postgres, the lab and the sandbox prerequisites (Docker), then `task dev` and `task web`.
3. Create an incident for a manifest case, open it in the UI and press Investigate.

With no manifest or provider key the API answers 503 and the UI says that no model provider is configured. **Status:** tested with a fake gateway and component tests only; the default real-sandbox path has not been run live against a real provider, and it spends provider tokens when it does.

## Layout

```
backend/traceforge/     one folder per feature (health/, contracts/, ...); main.py only wires routers
backend/tests/          pytest
frontend/               reviewer UI (Vite + React + TypeScript)
lab/, datasets/         victim lab services, generated cases, frozen manifests
scripts/                final-evaluation and scheduler scripts
results/, runs/         evaluation outputs, ledgers, logs (data, not code)
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
