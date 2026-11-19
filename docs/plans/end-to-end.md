# TraceForge end-to-end plan

Two people, two parallel tracks, equal work. Each person owns a set of folders, so the two of you never edit the same files. The tracks meet only through **shared contracts** (Pydantic schemas) agreed in step 00. Until the other side is ready, each side works against **sample JSON files** that follow those contracts.

- **Track A — Rafique: "evidence side"** (failure → evidence → ranked context → verified test result).
- **Track B — Ruhan: "agent side"** (context → diagnosis → patch → report → UI).

Each step becomes one Synverk card when it starts. Each person works one card at a time in their own lane.

## Who owns which folders

| Rafique (Track A) | Ruhan (Track B) | Shared (PR reviewed by both) |
|---|---|---|
| `lab/` | `backend/traceforge/incidents/` | `backend/traceforge/contracts/` |
| `datasets/` | `backend/traceforge/agent/` | `backend/traceforge/main.py`, `config.py`, `database.py` |
| `backend/traceforge/evidence/` | `backend/traceforge/repair/` | `pyproject.toml`, `Taskfile.yml`, root `compose.yaml` |
| `backend/traceforge/codeintel/` | `backend/traceforge/reviews/`, `reports/` | `docs/`, `README.md` |
| `backend/traceforge/retrieval/` | `backend/traceforge/github/` | |
| `backend/traceforge/sandbox/` | `frontend/` | |
| `backend/traceforge/evaluation/` | | |

## The contracts (step 00 — the only real dependency)

| Contract | Produced by | Consumed by |
|---|---|---|
| `CaseManifest`: one fault case (id, split, class, gold keys/spans, reproducer and hidden-test IDs) | A (generator) | B (agent runs, eval harness) |
| `EvidenceBundle`: evidence items for an incident (logs, health, redacted config, trace frames) | A (collector) | B (agent tools) |
| `ContextBundle`: ranked code/config hits with citations and token count, for mode L or G | A (retrieval) | B (agent prompt) |
| `TestRunRequest` → `TestRunResult`: run visible or hidden tests on a worktree in the sandbox | A (sandbox runner) | B (repair loop) |
| `AgentRunRecord`: diagnosis, patch, attempts, tokens, cost, latency, outcome | B (agent) | A (metrics, results) |

Each contract ships with 2–3 sample JSON files in `backend/traceforge/contracts/samples/`, so each side can build and test without waiting for the other.

## Assignment 3

### Step 00 — together (half a day)
| # | Step | Owner | Done when |
|---|---|---|---|
| 00a | Contracts + samples (table above) | Both, pair session | Schemas merged; samples validate in a test. |
| 00b | Backend scaffold: uv project, FastAPI `/health`, settings, Postgres in Compose, Taskfile, ruff/pytest | Rafique | `task dev` runs API + DB; `task test` passes. |
| 00c | Frontend scaffold: Vite + React + TS, pnpm, calls `/health`; proposal update (2-member team, new models, RTX 3050, design fixes) sent to supervisor | Ruhan | `task web` shows API status; revised PDF sent. |

### Phase 1 — parallel
| # | Rafique (Track A) | # | Ruhan (Track B) |
|---|---|---|---|
| A1 | **Lab fixtures**: `shop-api` (FastAPI + Postgres, documented contracts) and `worker` (Redis queue consumer), public tests, health/heartbeat probes. | B1 | **Incidents API + DB**: SQLAlchemy models, Alembic, `POST/GET /incidents`, state machine with transition guard, audit events. |
| A2 | **Sandbox runner**: run visible/hidden tests on a worktree in a limited container (no socket, no network, CPU/mem/time caps) → `TestRunResult`. | B2 | **Model gateway**: one OpenAI-compatible client for Mistral, Ollama, Groq; tool schemas; token/latency/cost log; smoke test; pin model (ADR). |
| A3 | **Fault generator**: config + code mutation templates, `CaseManifest`, `task dataset:validate` (buggy fails, original passes). First 4 cases: config, code, runtime_dependency, insufficient_evidence. | B3 | **Agent controller**: phased typed tools reading `EvidenceBundle`/`ContextBundle` (samples for now), hypothesis schema, abstain and runtime_dependency outputs, budgets, audit. |

**Sync 1:** B3 runs on A3's 4 real cases (still using sample evidence/context).

### Phase 2 — parallel
| # | Rafique (Track A) | # | Ruhan (Track B) |
|---|---|---|---|
| A4 | **Evidence collector**: read-only socket proxy, container status/health, log window, redacted effective config, traceback parser, SHA pin → `EvidenceBundle`. | B4 | **Repair loop**: diff parser + path policy, disposable worktree, calls A2 runner; F0/F1 with 3 attempts; visible-test feedback only; hidden suite once at the end. |
| A5 | **Code graph**: AST symbols/imports/calls, config-key reads, Compose services/env, test→symbol, trace frame → symbol, provenance. | B5 | **Report + review**: templated report from evidence; approve/reject bound to patch hash; tampered hash rejected. |
| A6 | **Retrieval L and G** → `ContextBundle`: BM25 + trace anchor in both arms; graph distance, ≤2-hop expansion, config binding in G; equal token budget; `task eval:retrieval` (E1). | B6 | **GitHub intake**: fixtures repo with issues; issue URL → incident (read-only token). |

**Sync 2:** full pipeline on the 4 cases. Real evidence → real context → agent → patch → hidden tests → report.

### Phase 3 — parallel
| # | Rafique (Track A) | # | Ruhan (Track B) |
|---|---|---|---|
| A7 | **Dataset scale-up**: ≥60 config, ≥60 code, ≥12 runtime_dependency, ≥12 insufficient_evidence held-out; ≥30 dev; freeze + hash. | B7 | **Frontend**: incident list/create, timeline, evidence, ranked hits, diff, test results, approve/reject. |
| A8 | **Evaluation metrics**: Recall@5/MRR/nDCG, diagnosis accuracy, abstention precision, verified repair rate, latency/cost from `AgentRunRecord`s; failure-analysis table. | B8 | **Experiment runner + results page**: batch-runs the agent over a manifest for a condition (L0/G0), saves `AgentRunRecord`s; UI page renders A8's metrics. |

**Sync 3 — together:** run the A3 evaluation (E1 on all cases; L0 vs G0 on ≥50), write ≥10 failure analyses (split by track: each analyses failures in their own part), build the demo script and submission pack, and dry-run from a clean clone.

## Assignment 4 — same lanes

| Rafique (Track A) | Ruhan (Track B) |
|---|---|
| A9 Deeper graph edges (runtime trace edges, cross-service config) + more fault families | B9 Full 2×2 × 3 runs orchestration (L0/G0/L1/G1) |
| A10 Statistics: paired bootstrap CIs, McNemar, interaction | B10 Model sensitivity: Devstral vs local Qwen2.5-Coder-7B |
| A11 Hardening: prompt-injection fixtures, sandbox limits, secret/path tests | B11 CI (GitHub Actions), two-stage images, public deployment of the app |
| A12 Optional BugsInPy subset, reported separately | B12 UI polish, review audit view |
| Paper: method (graph, retrieval), dataset, evaluation sections | Paper: system, agent, repair, deployment sections; investor pitch |

## How you work in parallel on GitHub
- `main` is protected: changes land only through a pull request with one approval.
- Branch per card: `rafique/A4-evidence-collector`, `ruhan/B4-repair-loop`.
- Each PR is reviewed by the **other** person. This keeps the work equal in the Git history and means both of you can explain every part in the viva.
- A change to a shared file (contracts, `main.py`, `pyproject.toml`, Taskfile) is its own small PR, merged before the work that needs it.

## Cost and limits (USD 0)
- Mistral free tier for experiments (confirm limits in its admin panel during B2). Free-tier prompts may be used for training; acceptable because fixtures are synthetic.
- Local Ollama as comparator and fallback; Groq as a spare.
- Paid-customer estimate for the business section: Mistral Large list price $0.50/1M input, $1.50/1M output → ~$7/month tokens at 300 incidents.

## Open risks
- Free-tier limits or terms change → Ollama keeps everything runnable; record any switch as an ADR.
- Local 7B tool calling too weak → still a valid comparator; report honestly.
- Synthetic faults too easy → decoys, ambiguous pairs, per-family results.
- Contract change mid-phase → shared-file PR first; the other person updates their samples the same day.
