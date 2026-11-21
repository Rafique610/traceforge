# File-by-file reference (implemented, project-owned files)

Back to [TraceForge Explained](TraceForge-Explained.md). Paths are relative to the repo root `D:\TraceForge\repo`. Generated or third-party files (`uv.lock`, `pnpm-lock.yaml`, `contracts/schema/*.json`, caches, `__pycache__`) are not described. "Tests" names the test file that covers the code. Line counts are from the working tree on 2026-11-21.

## Backend app core

| File | Purpose | Main items | Tests |
|---|---|---|---|
| `backend/traceforge/main.py` (10 lines) | Creates the FastAPI app, includes health and incidents routers, registers the 409 handler | `app` | `tests/test_health.py` |
| `backend/traceforge/config.py` (56) | The only reader of environment variables | `Settings` (prefix `TRACEFORGE_`, reads root `.env`), `get_settings()` (cached), `database_url` property | used by all tests |
| `backend/traceforge/database.py` (22) | DB engine, session factory, ORM base | `engine` (3 s connect timeout, `pool_pre_ping`), `SessionLocal`, `Base`, `get_db()` | `tests/test_health.py` |
| `backend/traceforge/__init__.py` | Holds `__version__` (used by `/health`) | `__version__` | `tests/test_health.py` |
| `backend/alembic/env.py`, `alembic.ini` | Alembic setup; the DB URL comes from `Settings`, never from `alembic.ini` (README) | `run_migrations_online/offline` | none |
| `backend/alembic/versions/0001_incidents.py` | Hand-written migration for the 3 incident tables. Its header says "NOT yet applied on Postgres" | `upgrade/downgrade` | `tests/incidents/test_postgres.py` (skipped without Postgres) |
| `compose.yaml` | Postgres 16 container for the app only (credentials via `${VAR}` from `.env`) | service `db`, volume `db-data` | n/a |
| `Taskfile.yml` | All routine commands | see [setup](setup.md) | n/a |

Settings snippet (`backend/traceforge/config.py`), showing the free-only guard fields:

```python
    # Hard guard against paid use: only allowlisted providers, openrouter ids must end ':free'.
    llm_free_only: bool = True
    llm_free_allowlist: frozenset[str] = frozenset({"ollama", "openrouter"})
```

## Health (`backend/traceforge/health/`)

| File | Purpose | Main items |
|---|---|---|
| `router.py` | `GET /health`: returns `ok/up`, or `degraded/down` when `SELECT 1` fails | `health()` |
| `schemas.py` | Response model | `HealthResponse(status, db, version)` |

Tests: `backend/tests/test_health.py` (`test_health_ok_when_db_up`, skipped if Postgres is not running; `test_health_degraded_when_db_down`).

## Contracts (`backend/traceforge/contracts/`)

| File | Purpose | Main classes |
|---|---|---|
| `__init__.py` | Re-exports and the `CONTRACTS` registry (6 entries) | `CONTRACTS` |
| `case_manifest.py` | One fault case with its true answer | `CaseManifest`, `GoldSymbol`, `CauseClass`, `REPAIRABLE` |
| `evidence.py` | Read-only facts | `EvidenceBundle`, `EvidenceItem` |
| `context.py` | Retrieval output | `ContextBundle`, `ContextHit` |
| `test_run.py` | Sandbox request/response | `TestRunRequest`, `TestRunResult`, `TestOutcome` |
| `agent_run.py` | One agent run's record | `AgentRunRecord`, `Diagnosis` |
| `export_schema.py` | Writes JSON Schema to `schema/` (`task contracts:schema`) | script |
| `samples/*.json` | 18 sample files: `config`, `code`, `abstain` for each of the 6 contracts | data |

Tests: `backend/tests/test_contract_samples.py` (`test_three_samples_per_contract`, `test_sample_validates_and_round_trips`, `test_repairable_case_needs_target`, `test_context_within_budget`, `test_windows_paths_rejected`, `test_diagnosis_must_cite_evidence`).

## Incidents (`backend/traceforge/incidents/`)

| File | Purpose | Main items |
|---|---|---|
| `states.py` | The 13 states and the allowed-move map | `State`, `ALLOWED` |
| `models.py` | ORM tables | `Incident`, `EvidenceItemRow` (key = incident id + EV id), `AuditEvent` (insert-only) |
| `schemas.py` | Request/response models with limits | `IncidentCreate` (needs `case_id` or `symptom`+`service`), `IncidentOut`, `IncidentPage`, `AuditEventOut`, `EvidenceItemOut` |
| `repository.py` | All DB access; no update/delete for audit events | `add_incident`, `get_incident(lock=)`, `list_incidents`, `add_event`, `list_events`, `list_evidence`, `save_evidence_bundle` |
| `service.py` | Business rules | `create_incident`, `transition`, `_guard_failure`, `IllegalTransition`, `IncidentNotFound` |
| `router.py` | HTTP endpoints, 409 handler | `register_handlers`, 5 endpoints (see [architecture](architecture.md)) |

Tests (`backend/tests/incidents/`): `test_incidents_service.py` (`test_every_state_pair` checks every pair of states, guards, audit hash, append-only API, same EV id in two incidents), `test_incidents_api.py` (201/404/422/409, pagination), `test_postgres.py` (concurrent transitions: only one wins; skipped without Postgres), `conftest.py` (SQLite fixtures).

Note on tests: the main suite runs on **SQLite**; row locking (`FOR UPDATE`), JSONB and the migration are Postgres-only behaviours and are listed as unverified in `docs/plans/RUHAN_CHECKLIST.md`.

Snippet (`backend/traceforge/incidents/states.py`):

```python
    S.DIAGNOSED: {S.PATCH_PROPOSED, S.REVIEW_PENDING},
    S.INCONCLUSIVE: {S.REVIEW_PENDING},
    S.PATCH_PROPOSED: {S.VALIDATING},
    S.VALIDATING: {S.VERIFIED, S.UNVERIFIED},
```

## Agent (`backend/traceforge/agent/`)

| File | Purpose | Main items |
|---|---|---|
| `gateway.py` (195) | One call path to any OpenAI-compatible provider | `chat()`, `check_allowed()`, `tool_calls_from_text()`, `make_client()`, `GatewayError`, `ModelResponse`, `ToolCall` |
| `cache.py` | One JSON file per request hash under `llm_cache_dir/<provider>/<model>/<xx>/` | `cache_key`, `get`, `put` |
| `call_log.py` | Append-only JSONL log with counts only | `log_call` |
| `pipeline.py` | The orchestration | `run_case()`, `Sources`, `sample_sources()` |
| `diagnose.py` | Tool loop (max 6 calls) | `diagnose()`, `Usage`, `DiagnoseResult` |
| `patch.py` | One patch request, diff extraction | `request_patch()`, `extract_diff()` |
| `tools.py` | Typed read-only tools with validation | `ReadEvidence`, `ReadSymbol`, `GetNeighbors`, `SubmitDiagnosis`, `dispatch()`, `tool_schemas()`, `ToolContext.allowed_path` |
| `prompting.py` | Loads prompt templates, hashes them, renders evidence and context | `load`, `prompt_hash`, `render_evidence`, `render_context` |
| `prompts/diagnose_v1.md`, `patch_v1.md` | Versioned prompts ("---USER---" splits system and user parts) | templates |
| `sources.py` | The three source interfaces and sample-JSON versions | `CaseSource`, `EvidenceSource`, `ContextSource`, `Sample*Source` |
| `run.py` | CLI: run samples under a condition, save records | `main()` |
| `smoke.py` | Live round-trip test with one tool, run twice to prove caching | `main()` |

Tests (`backend/tests/agent/`): `test_gateway.py` (cache hit/miss, retry on 429, fail fast on other errors, price calc, stable key, replicate index changes the key, free-only guard, no secret or content in logs, prompt-too-long, JSON-text tool call), `test_pipeline.py` (happy paths for code and config, abstain makes no patch, `runtime_dependency` makes no patch call, invalid args counted, unknown evidence rejected, budget exhaustion, malformed output, provider failure, prompt-injection test, hidden tests never in prompts, context budget, stable prompt hash, incident states advance), `conftest.py` (`FakeChat`).

Snippet (`backend/traceforge/agent/gateway.py`), the free-only guard:

```python
def check_allowed(s: Settings) -> None:
    if not s.llm_free_only:
        return
    if s.llm_provider not in s.llm_free_allowlist:
        raise GatewayError(f"free_only: provider '{s.llm_provider}' is not allowlisted")
    if s.llm_provider == "openrouter" and not s.llm_model.endswith(":free"):
        raise GatewayError("free_only: openrouter model id must end with ':free'")
```

Snippet (`backend/traceforge/agent/tools.py`), the path allowlist for the model's tools:

```python
    def allowed_path(self, path: str) -> bool:
        parts = path.split("/")
        return path.startswith(f"lab/{self.case.service}/") and ".." not in parts
```

## Repair (`backend/traceforge/repair/`)

| File | Purpose | Main items |
|---|---|---|
| `__init__.py` | Exports | `run_repair`, `RepairResult` |
| `edits.py` | Parse and apply SEARCH/REPLACE blocks, make a unified diff | `parse_blocks`, `apply_edits`, `to_unified_diff`, `EditError` |
| `policy.py` | Reject unsafe patches with explicit reasons | `check_paths`, `check_patch`, `PolicyResult`, `MAX_CHANGED_LINES=60`, `MAX_FILES=2` |
| `worktree.py` | Disposable `git worktree` at `base_sha`, apply diff, always clean up (`subprocess` git, no shell) | `worktree()`, `read_base_file`, `WorktreeError` |
| `loop.py` | The attempt loop | `run_repair()`, `RepairResult`, `Attempt` |

Tests (`backend/tests/repair/`): `test_policy.py` (paths, symlinks, too many files, oversize/binary/syntax, ambiguous or non-matching blocks, diff round trip, test-literal check), `test_loop.py` (real correct patch verified, real wrong patch rejected by hidden suite, worktrees cleaned up, equal attempts for F0 and F1, hidden tests never leaked and run once, early stop, timeout is `UNVERIFIED`, fault not reproduced, invalid edits use attempts, literal special-casing rejected), `conftest.py` (toy repo fixture).

Snippet (`backend/traceforge/repair/loop.py`), the baseline check:

```python
    if not _clean(base):
        res.outcome, res.reason = "UNVERIFIED", "sandbox_error"
        return res
    if _green(base) or base.failed == 0:
        res.outcome, res.reason = "UNVERIFIED", "fault_not_reproduced"
        return res
```

## Frontend (`frontend/`)

| File | Purpose | Tests |
|---|---|---|
| `src/main.tsx`, `src/App.tsx` | Entry point; header with `HealthBadge` and an "Incidents / No incidents yet" placeholder | none |
| `src/health/HealthBadge.tsx` | Fetches `/health`; states `loading`, `ok`, `degraded`, `unreachable` | `HealthBadge.test.tsx` (5 `it` cases: loading, ok, degraded, unreachable on network error, unreachable on non-2xx) |
| `src/shared/api.ts` | `apiGet<T>()`; base is `VITE_API_URL` or `/api` | via the badge test |
| `src/index.css`, `src/test-setup.ts` | Styles; Testing Library matchers | n/a |
| `vite.config.ts` | Dev proxy: `/api/*` to `http://localhost:8000/*` (prefix stripped); Vitest with jsdom | n/a |
| `package.json`, `tsconfig*.json`, `.oxlintrc.json`, `index.html` | Tooling config | n/a |

Snippet (`frontend/src/health/HealthBadge.tsx`):

```tsx
function toState(h: Health): State {
  return h.status === 'ok' && h.db === 'up' ? 'ok' : 'degraded'
}
```

## Other files

| File | Purpose |
|---|---|
| `spikes/retrieval/**` | Rafique's feasibility prototype (toy shop, BM25/graph ranking, saved `results/retrieval.json`). Not product code. See [research log](research-log.md). |
| `backend/runs/llm_calls.jsonl`, `backend/.cache/llm/...` | Real artifacts of the local smoke run (git-ignored outputs) |
| `.env.example` | Names of settings only; never put values in it |
| `AGENTS.md`, `PROMPT.md`, `docs/**` | Rules, plans, orchestration; `docs/guide/` is this encyclopedia |
