# Rafique-owned components that Ruhan's tasks depend on (scope-limited)

Written 2026-11-21 after the owner's scope clarification: implement ONLY the Rafique-track components that Ruhan's tasks genuinely need; leave Rafique's unrelated tasks to him. Original owner and implementer are recorded separately. Statuses use the project vocabulary; nothing here is "Verified complete" without Ruhan's approval.

## A. Prerequisites (implementation authorised, strictly limited)
| Ruhan task needing it | Rafique component | Why required | Interface needed | Existing before? | Implementer / current state (2026-11-21) |
|---|---|---|---|---|---|
| P1-S07, P2-S04, P3-S04, P4-S01, P5-S03 | **P1-S01 Lab** (`lab/`) | the victim system the whole pipeline diagnoses; seed cases and hidden tests are built on its code | services shop_api + worker + lab compose; public visible tests; probes | No (only a spike toy shop) | Claude-assisted session for Ruhan. **In progress:** ~48 files under `lab/` exist; agent interrupted by usage limit; compose bring-up and test runs NOT yet verified |
| P2-S04 (repair loop), P1-S07 | **P1-S02 Sandbox** (`backend/traceforge/sandbox/`) | verifies patches in an isolated container; the repair loop currently uses a test-only stand-in runner that may not count as integration evidence | `run_tests(TestRunRequest) -> TestRunResult`; hidden tests outside worktree; limits, no network | No | Claude-assisted session. **In progress:** 7 source files + 14 test-support files exist; agent interrupted; tests NOT yet run/verified |
| P1-S07, P2-S04, P3-S04 | **P1-S03 Fault generator + seed cases** (`datasets/`) | real `CaseManifest`s with gold labels, visible/hidden tests, `base_sha` | manifest JSON list, hidden tests dir, validator (3× runs) | No | Not started |
| P1-S06 → real evidence for my agent | **P2-S01 Evidence collector** (`backend/traceforge/evidence/`) | produces the `EvidenceBundle` (logs, health, effective config, trace frames, redaction) my agent consumes via `EvidenceSource` | `collect(incident_id, service, case) -> EvidenceBundle` | No | **Implemented + verified against the real lab (2026-11-21)**: 67 tests (21 need the running proxy/lab; all passed), live evidence from a real worker failure (bad REDIS_HOST) and a real shop_api DB-down 500; proxy refuses 18/18 write calls; no secret leaks; deterministic ids/hashes. NOT done: CLI, seed-case bundles (need P1-S03), live JSON/uvicorn-access logs |
| G arm of the 2×2 (P3-S04 conditions, P4-S01, P5-S03) | **P2-S02 Code graph** (`backend/traceforge/codeintel/`) | graph retrieval is experimental factor G | `build_graph`, `distance`, `neighbors`, `code_map`, impact set | spike only | Claude-assisted session. **In progress:** 9 source files exist, **no tests yet**; agent interrupted |
| P1-S06 real context, P3-S04, P4-S01 | **P2-S03 Retrieval L and G** (`backend/traceforge/retrieval/`) | produces the `ContextBundle` (L = BM25 + trace anchor; G adds graph) for both conditions and the E1 retrieval benchmark | `retrieve(evidence, graph, mode, token_budget) -> ContextBundle` | spike only | Not started |
| P3-S04 results page, P4-S01 | **P3-S02 Metrics + baseline** (`evaluation/{metrics,baselines,analysis}`) | computed metrics for the results page and experiments | `report(records, manifests, contexts)`; GET /evaluation/report | No | **Implemented** by Claude-assisted session: 25 new tests; **not run on real data**; CLI/router tested on hand-built runs only |
| P4-S01, P5-S03 | **P3-S01 Dataset scale-up and freeze** (`datasets/`) | the frozen test set + dev set the experiments must run on | manifests dev/test, `test.sha256`, ≥60/60/12/12 + ≥30 dev, ≥50% distance ≥1 | No | Not started (largest item; may only be partly achievable) |
| shared | `AgentRunRecord` contract (B9, B13) | needed for provider-agnostic gateway and RULES baseline | additive fields | existed | Changed additively by Claude-assisted session; **Rafique has not been told** |

## B. Rafique's tasks NOT needed for Ruhan's tasks (left to Rafique, not touched)
| Task | Why not a prerequisite |
|---|---|
| P2-S07 Sync 2 (primary Rafique) | Integration checkpoint; Ruhan wires the consumer side, Rafique leads the joint session |
| P4-S02 Failure analysis and results | Analysis of results after experiments; his authorship |
| P5-S01 Deeper graph + new fault families | Phase 5 research extension |
| P5-S02 Statistics (A4) | Phase 5 research statistics beyond the metrics needed for the A3 results page |
| P5-S05 BugsInPy subset (optional) | Optional |
| P6-S01 Security hardening | Phase 6; Ruhan's tasks do not need the full suite |
| P6-S04 Paper (primary) | Writing |
| P0-S01 / P0-S02 | already his and done / pending his collaborator step |

## C. Genuine external blockers (still)
- Supervisor written approval (P0-S04, Q3); proposal PDF from Ruhan.
- Devstral free access: Ollama account balance unknown until the API key balance check runs (key now in `.env` as `OLLAMA_API_KEY`); Mistral Experiment plan unchecked.
- **Claude Code usage limit** hit at ~19:50 local time; resets 9 pm Asia/Karachi. Three implementation agents (lab, sandbox, code graph) stopped mid-work; their saved files must be re-validated, not trusted.

## D. Status update — end of day 2026-11-21 (evidence-based)
| Component (original owner) | Implemented by | Verified how (real systems) | Limits |
|---|---|---|---|
| P1-S01 Lab (Rafique) | Claude-assisted session for Ruhan | real compose stack healthy; order created via API and confirmed by worker; 37 visible + 3 integration tests; non-root, read-only, cap-drop; Redis stop → /health 503 | silent fault handling found by the E2E run (no tracebacks) → being fixed |
| P1-S02 Sandbox (Rafique) | same | 19 tests, 12 in real containers: network off, read-only fs, fork bomb/OOM/loop limits, no socket, hidden suite isolation, selftest medians ~2.2 s/run | worker-service tests not runnable yet |
| P1-S03 Seed cases (Rafique) | same | 4 dev cases validated in the real sandbox, 3× each, no flips; gold fix turns hidden tests green | 4 cases only; distances manual; no frozen test split |
| P2-S01 Evidence (Rafique) | same | 67 tests; live collection from real failing lab; proxy refuses 18/18 writes; no secret leak; deterministic ids | case 004 hint (suppressed logs) cannot be honoured by the collector; health probe timeouts |
| P2-S02 Code graph (Rafique) | same | 26 tests; real backend + lab graphs; config bindings resolved | call-resolution precision not measured |
| P2-S03 Retrieval (Rafique) | same | 24 tests; G beats L on config-key binding in a lab test; E1 on real evidence: 2 cases, all methods ~0 (thin evidence) | E1 not meaningful until traces exist |
| P3-S02 Metrics (Rafique) | same | 25 new tests vs hand-computed values; run on real run records (10 records) | edit-quality metrics unavailable |
| P3-S01 Frozen dataset (Rafique) | NOT done | — | needs far more validated cases (≈3 min each in the real sandbox); not padded |
Rafique's untouched tasks (unchanged): P2-S07, P4-S02, P5-S01, P5-S02, P5-S05, P6-S01, P6-S04, P0-S01/S02.
