# TraceForge architecture

**Labels:** sections marked CURRENT describe code that exists; sections marked PROPOSED are not implemented and not approved. Last synced 2026-11-25.

Backend: FastAPI + SQLAlchemy/Alembic (Postgres) in `backend/traceforge/`; `main.py` only wires routers. Frontend: React reviewer UI in `frontend/`.

## Backend modules (CURRENT)
| Module | Role |
|---|---|
| `agent/` | Pipeline v5: symptom derivation, diagnosis loop (model + local read-only tools), patch stage, prompts, model gateway (`gateway.py`), providers (`axforge.py` with ledger/pacing/slots, `beatapi.py`), call log, persistence (`persist.py`, `e2e.py` CLI that stores a real run for the UI). |
| `retrieval/` | Lexical (L) and graph (G) rankers, symptom-derived anchors, corpus, token-budgeted context packing. |
| `codeintel/` | Code graph (symbols, calls, config references, compose graph, test map) used by the G arm. |
| `evidence/`, `diagnostics/` | Evidence collection (logs, health, effective config, tracebacks) with scope/basis/origin labels; deterministic hint rules emitted as FINDING items. |
| `repair/` | Edit model, scope policy, guard (leak guard), visible-test feedback, worktree, repair loop (up to 3 attempts). |
| `sandbox/` | Isolated Docker test execution (visible and hidden suites). |
| `evaluation/` | Conditions (`conditions/L0,G0,L1,G1.json`), runner, metrics, analysis, final-report tool, fingerprint gate, usage report, two-slot job scheduler. |
| `incidents/`, `reviews/`, `reports/`, `github/` | Incident state machine (illegal transitions give 409), hash-bound approve/reject review, evidence report, GitHub intake. |
| `health/` | `GET /health` (status, database up/down, version). |
| `contracts/` | Shared data shapes (CaseManifest, EvidenceBundle, ContextBundle, TestRun*, AgentRunRecord) with samples and JSON Schema. |
| API | Routers: health, incidents, github, reports, reviews, evaluation. `POST /incidents/{id}/investigate` (`investigation.py`) starts a background job (`run_case_with_repair` then `save_outcome`) and answers 202; 404 unknown incident, 409 wrong state, 422 bad input or unknown case, 503 when `TRACEFORGE_MANIFEST` or a provider key is missing. The factory is injectable (tests use a fake gateway); the default real-sandbox factory is untested live. |
| `agent/rc2/` (CURRENT, opt-in) | RC2 candidate pieces: rationale truncation, repeat guard, config-value checker (standalone), version tag; `select_chat_fn("rc1"\|"rc2")` wraps the chat function, default rc1, and nothing calls it yet. Not validated; owner approval pending. RC1 fingerprint unchanged; RC2 fingerprint in `results/rc2/rc2-fingerprint.txt`. |
| `agent/hw_monitor.py` (CURRENT) | Samples GPU and RAM during local-model runs (P5-S04). |

## Data flow of one case-run
1. Load the case from the frozen manifest; the code fingerprint and split hash are checked first (final mode).
2. Run the visible tests on the base commit; derive and redact the symptom.
3. Collect evidence and deterministic findings.
4. Retrieve context (L or G) and pack it under the token budget.
5. Diagnose: model requests through the gateway; tool calls are local; claims and targets validated.
6. Patch: model proposes scoped edits; the visible tests run in the sandbox. In `1` conditions a failed attempt yields feedback (visible-only, with provenance) for attempts 2-3.
7. Freeze the final patch; run the hidden suite once; record the AgentRunRecord (with fingerprint, feedback provenance, guard hits).
8. For review: the evidence report is persisted with the diff hash; approval re-hashes the stored diff (409 on mismatch) and refuses patches that did not reach VERIFIED.

## Conditions
Retrieval arm x feedback: L0 (lexical, none), G0 (graph, none), L1 (lexical, visible-test feedback), G1 (graph, feedback). In the final evaluation L1 and G1 start from the saved, hash-verified diagnosis of the L0/G0 run of the same case and replicate, so feedback is the only difference.

## Safeguards
- **Leak guard:** hidden-only test names are blocked everywhere; shared names are allowed only in feedback/symptom/finding spans, the model's own words and the diagnosis lines; hidden runs cannot produce feedback; the frozen patch cannot be reassigned after the hidden run.
- **Frozen split:** `datasets/manifests/test.json` is hash-checked against `test.sha256`; case selection is seeded and recorded before any model call; RC1 behaviour files are fingerprinted and a changed fingerprint stops the run.
- **Pacing (AxForge):** 30 s start-to-start per key slot, kept in a per-slot file shared across processes; Retry-After blocks the slot; no SDK or gateway retries; first failure halts the slot.
- **Ledger:** per-slot append-only token ledger (`runs/axforge_usage*.jsonl`); a request that could cross the ceiling (committed + input estimate + max output) is refused before sending. Authorization to call AxForge lives only in process memory. Details: `docs/research/dual-key-operations.md`, `docs/research/axforge-pacing-audit.md`.
- **Hash-bound review:** see step 8 above.

## Retrieval architecture (CURRENT and PROPOSED)
Retrieval today is BM25 over graph-derived chunks (L) plus a 2-hop graph walk (G), rebuilt per process, with no embeddings and no persisted index; RC1 is frozen. A **proposed** offline follow-up study (not approved, not in the product path) would add a dense arm, reciprocal-rank fusion and an incremental content-addressed embedding index in new modules, decided by ADR 0003 after a dev-split benchmark. See [plans/ARCHITECTURE.md](plans/ARCHITECTURE.md#retrieval-architecture-current-and-proposed-target) and [research/retrieval-architecture-review.md](research/retrieval-architecture-review.md).

## Root-cause traversal, impact report and regression validation (PROPOSED, not implemented)
Current architecture is unchanged. A **proposed** (25 Nov 2026, pending owner approval) offline follow-up adds, in new modules working on a graph copy: an overlay with evidence classes (`static`, `observed`, `inferred`, `unknown`), budgeted bidirectional traversal with a candidate ranker (P5-S12), a change-impact report with visible-test selection (P5-S15), and, conditionally and RC2 only, regression-aware validation in the repair loop (P5-S17). Evaluated against preregistered thresholds (P5-S16), not guaranteed; hidden tests never enter graph, report or feedback. See [plans/ARCHITECTURE.md](plans/ARCHITECTURE.md#root-cause-traversal-impact-report-and-regression-validation-proposed-25-nov-2026) and [research/root-cause-impact-regression-design.md](research/root-cause-impact-regression-design.md).
