# Architecture

Status: **designed, not implemented.** Where this document and the earlier proposal architecture (`TraceForge_Architecture_Audited.md`, outside the repo) differ, this document reflects the decisions made after the supervisor review and is authoritative for implementation. Differences are listed in [DECISIONS_AND_OPEN_QUESTIONS.md](DECISIONS_AND_OPEN_QUESTIONS.md#contradictions-found).

## High-level view
```
 Reviewer UI (Vite + React)  ──REST──►  FastAPI control plane  ──►  PostgreSQL
                                             │
         ┌───────────────────────────────────┼─────────────────────────────────┐
         │ Track A (evidence side)            │ Track B (agent side)             │
         │  evidence   ◄── read-only proxy ── Docker lab (shop-api, worker,     │
         │  codeintel  ◄── lab source @SHA        postgres, redis)               │
         │  retrieval  ─► ContextBundle ──────►  agent (pipeline + gateway)      │
         │  sandbox    ◄── TestRunRequest ─────  repair (worktree, policy, loop) │
         │  evaluation ◄── AgentRunRecord ─────  reports / reviews / github      │
         └────────────────────────────────────────────────────────────────────────┘
                                             │
                     Mistral free API · Ollama (local) · Groq (spare)
```

## Components and owners
| Component | Folder | Owner | AI? | Responsibility |
|---|---|---|---|---|
| Contracts | `backend/traceforge/contracts/` | Shared | No | The five data shapes between tracks |
| App core | `backend/traceforge/{main,config,database}.py`, `health/` | Rafique | No | App factory, settings, DB session, `/health` |
| Lab | `lab/` | Rafique | No | Victim services with contracts, tests, probes |
| Dataset | `datasets/` | Rafique | No | Fault templates, manifests, hidden tests, validator |
| Sandbox | `backend/traceforge/sandbox/` | Rafique | No | Run test suites in locked-down containers |
| Evidence | `backend/traceforge/evidence/` | Rafique | No | Read-only collection, redaction, trace parsing |
| Code intelligence | `backend/traceforge/codeintel/` | Rafique | No | AST + Compose + config graph with provenance |
| Retrieval | `backend/traceforge/retrieval/` | Rafique | No (deterministic ranking) | L and G context bundles under one budget |
| Evaluation metrics | `backend/traceforge/evaluation/metrics/`, `baselines/`, `analysis/` | Rafique | No | Metrics, rule baseline, stats |
| Incidents | `backend/traceforge/incidents/` | Ruhan | No | Incident records, state machine, audit |
| Agent | `backend/traceforge/agent/` | Ruhan | **Yes** | Gateway, cache, pipeline, diagnose tools, patch request |
| Repair | `backend/traceforge/repair/` | Ruhan | No | Diff policy, worktrees, F0/F1 loop, hidden-test gate |
| Reports, reviews | `backend/traceforge/reports/`, `reviews/` | Ruhan | No | Deterministic report, hash-bound review |
| GitHub | `backend/traceforge/github/` | Ruhan | No | Issue → incident |
| Experiment runner | `backend/traceforge/evaluation/runner.py`, `conditions/` | Ruhan | No | Batch runs per condition |
| Frontend | `frontend/src/<feature>/` | Ruhan | No | Reviewer UI and results page |

## Data flow for one incident
1. **Intake** (`incidents`): `POST /incidents` (case or GitHub issue) → state `CREATED`.
2. **Snapshot** (`evidence`): pin `base_sha` + Compose hash → `SNAPSHOT_LOCKED`.
3. **Evidence** (`evidence`): build `EvidenceBundle` → `EVIDENCE_COLLECTED`.
4. **Context** (`codeintel` + `retrieval`): graph for `base_sha`; anchors from evidence; `ContextBundle` (L or G) → `CONTEXT_RETRIEVED`.
5. **Diagnose** (`agent`): LLM with read-only tools (≤6 calls) → hypotheses → `DIAGNOSED` or `INCONCLUSIVE`.
6. **Patch** (`agent` + `repair`): one LLM call → diff → policy check → worktree → `PATCH_PROPOSED`.
7. **Verify** (`repair` → `sandbox`): visible tests per attempt (≤3; F1 feeds output back), hidden suite once → `VERIFIED` or `UNVERIFIED`.
8. **Report + review** (`reports`, `reviews`) → `REVIEW_PENDING` → `REVIEWED` → `CLOSED`.

State machine: `CREATED → SNAPSHOT_LOCKED → EVIDENCE_COLLECTED → CONTEXT_RETRIEVED → DIAGNOSED | INCONCLUSIVE → PATCH_PROPOSED → VALIDATING → VERIFIED | UNVERIFIED → REVIEW_PENDING → REVIEWED → CLOSED`. Guards: no `DIAGNOSED` without evidence IDs; no `VERIFIED` without a red/green pair; no `REVIEWED` without a matching patch hash. `runtime_dependency` goes `DIAGNOSED → REVIEW_PENDING` with no patch; `insufficient_evidence` goes `INCONCLUSIVE → REVIEW_PENDING`.

## Contracts
Defined in P0-S05; full field list in [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md#contracts). `CaseManifest`, `EvidenceBundle`, `ContextBundle`, `TestRunRequest`/`TestRunResult`, `AgentRunRecord`.

## API (planned)
| Method | Path | Step |
|---|---|---|
| GET | `/health` | P0-S02 |
| POST | `/incidents` | P1-S04 |
| GET | `/incidents`, `/incidents/{id}`, `/incidents/{id}/events` | P1-S04 |
| POST | `/incidents/{id}/investigate` | P2-S07 (wiring), P3-S03 (UI) |
| POST | `/incidents/from-github` | P2-S06 |
| GET | `/incidents/{id}/report` | P2-S05 |
| POST | `/incidents/{id}/review` | P2-S05 |
| GET | `/evaluation/runs`, `/evaluation/report` | P3-S04 |

Paths beyond these are **[TO BE DECIDED]** in their steps.

## Database (planned tables)
`incidents`, `evidence_items`, `audit_events` (insert-only) — P1-S04; `patches` (frozen diff + SHA-256), `validation_runs` — P2-S04; `reviews` (insert-only) — P2-S05; run records stored as JSON files under `runs/` (git-ignored) and optionally indexed in a table — P3-S04 **[TO BE DECIDED: file-only vs table]**. Graph and LLM cache live on disk keyed by SHA (`.cache/graph/`, `.cache/llm/`), not in Postgres, for A3.

## External services
| Service | Use | Notes |
|---|---|---|
| Mistral API (free tier) | Primary LLM, pinned Devstral model | Model ID and limits recorded in ADR 0001 (P1-S05) |
| Ollama (local) | Comparator `qwen2.5-coder:7b`, offline fallback | 6 GB VRAM |
| Groq (free tier) | Spare for small checks | ~200K tokens/day on gpt-oss-120b |
| GitHub REST | Issue intake | Read-only token or unauthenticated for public repos |

## Authentication and authorization
A3: single-user local app; the reviewer identity on a review is a name field. **[TO BE DECIDED]** whether A4's public deployment needs login (P6-S02). Service authority is enforced in code, not by the LLM: tool allowlist per stage, path allowlist for patches, read-only Docker proxy, sandbox-only execution.

## Error handling
- Validation errors → 422 via Pydantic schemas.
- Illegal state transitions → 409 with the current state.
- Provider errors/rate limits → gateway retries with backoff, then records `UNVERIFIED`/`INCONCLUSIVE` with a reason; never fabricates output.
- Sandbox failure to execute → `UNVERIFIED`, never counted as success.

## Configuration
All settings through `traceforge/config.py` (`Settings`, prefix `TRACEFORGE_`), backed by git-ignored `.env`; `.env.example` lists names only. Lab services have their own Pydantic settings. Compose files reference `${VAR}` only.

## Research design
- **Factor G:** L = BM25 + traceback anchoring; G = L + graph distance, ≤2-hop expansion, config-key binding. Same candidate generator and token budget.
- **Factor F:** F0 = up to 3 fresh attempts; F1 = up to 3 attempts with visible-test feedback. Hidden suite once at the end in both.
- Conditions L0, G0, L1, G1; fixed model, temperature 0, prompts, tools, budgets. A3: E1 (retrieval only, all cases) + L0 vs G0 on ≥50 cases. A4: full 2×2 × 3 replicates.
- Every case labelled with `distance` (graph hops symptom → cause); ≥50% of test cases distance ≥1; results by distance.

## Deployment
- **A3:** everything local via Docker Compose; reproducible from the repo (rubric C5 alternative to a public link).
- **A4:** public deployment of the reviewer app showing saved runs/reports; lab and sandbox stay local. Host **[TO BE DECIDED]** in P6-S02.
