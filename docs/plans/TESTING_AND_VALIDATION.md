# Testing and validation

Each step document has its own testing section. This page defines the levels, owners and the commands everything plugs into.

**Commands (created in P0-S02/P0-S03, extended per step):** `task test` (backend pytest), `task lint` (ruff), `task web:test` (Vitest), `task lab:test`, `task sandbox:selftest`, `task dataset:validate`, `task eval:retrieval`, `task eval:report`, `task eval:run`.

## Unit testing
| What | Owner | Approach | Success criteria |
|---|---|---|---|
| Contracts | Both | Load samples; round-trip JSON | All samples valid; round-trip identical |
| Settings, health | Rafique | pytest + `httpx` TestClient | `/health` 200; DB-down reported, not crashed |
| State machine | Ruhan | Table of legal/illegal transitions | Every illegal move raises; audit row per move |
| Redaction | Rafique | Strings with passwords, tokens, DSNs | No secret survives; non-secret allowlist kept |
| Traceback parser | Rafique | 3+ real lab tracebacks | Frames (path, line, function) exact |
| Graph edges | Rafique | One tiny fixture package per edge type | Expected edges present; dynamic calls `UNKNOWN` |
| Retrieval | Rafique | Fixed corpus + query | Deterministic ranking; equal budget L vs G |
| Gateway | Ruhan | Mocked provider responses; cache hit/miss | Same request → cache hit, 0 API calls |
| Tool validation | Ruhan | Unknown tool, bad args, oversize args | Rejected and counted as invalid |
| Diff policy | Ruhan | Path escape, test file, binary, oversize | All rejected with reason |
| Metrics | Rafique | Hand-computed examples | Exact match to hand values |
| Retrieval benchmark (P5-S06) | Rafique | Hand-computed metric cases; fixed-seed bootstrap; two runs identical; GraphFeatures-off equals L; leakage test (no hidden tests, patches, gold in chunks) | Metrics exact; byte-identical rankings; RC1 fingerprint `ee3d8d87...` unchanged **2026-11-25:** IMPLEMENTED, TESTED (25 tests). Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; tasks stay Rafique's. |
| Chunk manifest, embedding cache, verifier (P5-S07) | Rafique | Fake embedder; six scenarios (edit, add, delete, rename, import change, model upgrade); crash and resume; verifier on tampered index | Only changed chunks re-embedded; ACTIVE never partial; verifier flags edits, missing vectors, wrong dims **2026-11-25:** IMPLEMENTED, TESTED (17 tests; six scenarios, crash safety, dims refusal). |
| Dense and fusion arms (P5-S08) | Rafique | RRF on hand-computed lists; forced anchors first; dims mismatch raises; preregistered H1 to H4 | Thresholds reported pass/fail with CIs; ADR 0003 PROPOSED **2026-11-25:** done; preregistered NO-GO (H1 FAIL -0.094, H2 FAIL, H3 FAIL, H4 PASS); ADR 0003 PROPOSED, decision blank; retrieval-level evidence only. |
| Overlay, traversal, evidence classes (P5-S12) | Rafique | Overlay never mutates the source graph; inheritance incl. external base -> `unknown`; evidence class per edge; budgets and cycle safety; identical output on two runs | All pass; RC1 fingerprint unchanged **2026-11-25:** IMPLEMENTED, TESTED (41 analysis tests incl. S12/S15/S16); ranker preregistered NO-GO. |
| Config value flow (P5-S13) | Rafique | Positive and negative fixture per mismatch check; secret-named keys absent from graph, reports and logs | All pass; no secret value printed **2026-11-25:** NOT STARTED. |
| Runtime evidence (P5-S14) | Rafique | `observed` marks never create `static` edges; unresolvable frame stays `unknown`; dev-only oracle not importable from pipeline code | All pass **2026-11-25:** NOT STARTED. |
| Impact report and selection (P5-S15) | Rafique | Golden tests on fixture patches (signature change, removed symbol, config default change, untested dependant); limitation statement present; stable report hash; hidden-test directory isolation test for graph and selection | Goldens identical; no hidden path in any node, path or selection **2026-11-25:** IMPLEMENTED, TESTED; GO on fixtures (selection recall 1.0, 0.575 of suite, 0 hidden leaks, 0 false-positive warnings). |
| Evaluation suite (P5-S16) | Rafique, Ruhan (label check) | Fixture validator: every expected relationship resolves; thresholds file committed before the first run | Threshold results reported pass/fail with CIs **2026-11-25:** reduced suite IMPLEMENTED (23 fixtures); second reviewer label check open. Full CI-style backend suite run locally before the last changes: 1,120 passed, 36 deselected (`cd backend && TRACEFORGE_ENV=test pytest -m "not docker and not e2e"`); CI green on dd3fae2. P5-S17 regression layer: 40 regression + 17 rc2 + 3 rc2_e2e tests; no live model end-to-end run. |
| RC2 fixes (P5-S10) | Ruhan | Fake-gateway tests: long rationale, identical retry, candidate config values | RC1 still reproducible from cache; analysed sites not used as confirmation |
| UI components | Ruhan | Vitest + Testing Library | Renders API data; loading/error/empty states |

## Integration testing
See [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md#integration-testing). Owners: the checkpoint lead. Run on both laptops at each sync.

## System and end-to-end testing
| Scenario | Expected result | Owner |
|---|---|---|
| Config fault, distance ≥1 | Correct key; patch verified; report cites config + reading symbol | Rafique (case), Ruhan (pipeline) |
| Code fault | Correct symbol; reproducer red → green; hidden pass | Both |
| runtime_dependency decoy (DB stopped) | Diagnosed `runtime_dependency`; no patch | Both |
| insufficient_evidence | `INCONCLUSIVE`; report lists missing evidence | Both |
| GitHub issue intake | Incident created; issue stored as untrusted evidence | Ruhan |
| Review with tampered hash | 409; nothing stored | Ruhan |

Run through the UI for the demo (P4-S03) and through `test_pipeline_e2e.py` from cache in CI.

## Edge cases and error handling
- Lab container missing or unhealthy before collection → evidence records it; diagnosis may be `runtime_dependency`.
- Log window empty → `insufficient_evidence` path, not a guess.
- LLM returns malformed JSON or unknown tool → retry within budget, then `INCONCLUSIVE` with reason.
- Provider rate limit (429) → backoff, resume; never a fabricated record.
- Patch fails to apply → counted attempt; `REJECTED` after the attempt budget.
- Sandbox timeout → `UNVERIFIED`, never success.

## Security testing
| Test | Owner | When |
|---|---|---|
| Injected instruction in log/comment/issue doesn't change tools or outcome | Ruhan (P1-S06, P2-S06), Rafique (P6-S01 suite) | A3 basic, A4 full |
| Sandbox: no network, caps enforced, no socket | Rafique | P1-S02, P6-S01 |
| No secret in prompts, index, report | Rafique | P2-S01, P6-S01 |
| Hidden tests never in prompts | Ruhan | P2-S04 |
| Hidden-test directory absent from graph, overlay, impact report and test selection (asserted); no hidden or oracle data in any prompt or regression feedback | Rafique (P5-S12, P5-S15), Ruhan (P5-S17) | P5-S12, P5-S15, P5-S17 |
| Forbidden paths/test edits rejected | Ruhan | P2-S04, P6-S01 |

## Performance testing
- Sandbox run time per suite (P1-S02): recorded to size the A4 run budget.
- Per-case latency median/P95 and tokens per case: every run record; summarized in P4-S01.
- Local model tokens/s and VRAM peak: P5-S04.
No hard targets are set until first measurements exist (see open questions).

## AI evaluation (rubric stage D)
| Component | Test set | Metric | Baseline | Owner |
|---|---|---|---|---|
| Retrieval | All repairable test cases (≥120) with gold symbols/keys | Recall@5, MRR, nDCG@10, tokens, by distance | L vs G | Rafique |
| Diagnosis | All ≥144 test cases | Cause-class accuracy, exact-target top-1, abstention precision/recall | Rule-based baseline | Rafique (metrics), Ruhan (runs) |
| Repair | ≥50 repairable test cases (A3); all 120 (A4) | Verified repair rate, apply rate, regressions | L0 vs G0 (A3), 2×2 (A4) | Ruhan (runs), Rafique (metrics) |
| Retrieval modernization (follow-up, P5-S06 to P5-S09) | Dev split (33 cases), offline, gold for scoring only | Recall@K, Precision@K, MRR, nDCG, source-localization, evidence coverage, context tokens, latency; paired bootstrap 95% CIs at equal token budget | RET-L, RET-G (budget-matched) | Rafique |
| Root-cause and impact analysis (follow-up, PROPOSED, P5-S12 to P5-S16) | Hand-verified fixtures separate from the frozen test split, plus dev split | Root-cause top-1/3/5 and MRR; dependency recall/precision at equal tokens; affected-dependant recall; selection recall and fraction selected; false-positive warnings per patch; latency; paired bootstrap CIs | RET-L, RET-G and P5-S08 arms | Rafique (Ruhan verifies labels) |
| Every component | All runs | Median/P95 latency, cost (actual + list-price), failure rate | — | Both |

## Acceptance testing
- A3 acceptance = [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md#acceptance-criteria-whole-project) A3 list, verified in the P4-S03 dry run from a clean clone on the other member's laptop.
- A4 acceptance = A4 list, verified in P6-S04 before submission.
- Each step's Definition of Done is its own acceptance test; the reviewer checks it before approving the PR.

## Who runs what, when
| Moment | Required checks |
|---|---|
| Every PR | `task lint`, `task test` (+ `task web:test` if frontend touched); the step's own checks pasted on the card |
| Each sync | Integration tests on both laptops; Synverk proof recorded |
| Before freeze | `task dataset:validate` on all cases |
| Before demo/submission | Clean-clone dry run; every reported number recomputed from saved runs |

## Test evidence and status (2026-11-25)
Counts are from runs on 2026-11-25 unless noted; nothing here means a step is reviewed or approved.

| Suite | Result |
|---|---|
| Backend full CI-style run | 1022 passed, 4 skipped, 36 deselected (one failure fixed afterwards; CI then green). Earlier 983 passed / 21 skipped was before the 25 Nov changes |
| `tests/integration` (Sync 1: fake gateway, offline replay of `ManifestCaseSource`, route to pipeline to repair to report to review) | 7 passed |
| `tests/reports` / `tests/incidents` / `tests/reviews` / `tests/repair` | 13 / 196 / 20 / 64 passed |
| `tests/agent` (includes RC2 and hw_monitor) | 339+3 passed |
| `tests/regression` (impact provider, selection, runner, history, adapters, preregistration validator; real pytest temp repo) | 26 passed |
| Frontend vitest | 12 files, 78 tests; `tsc -b` clean; `vite build` ok; oxlint warnings only |
| Lint | ruff check and ruff format clean |
| Docker | api and web images build (456 MB, 74.1 MB); compose up healthy locally; migrations 0001/0002 applied; GET / and /api/health 200; POST 403 (showcase) |
| CI | CI run on 64073ca (origin/main) is green on all four jobs: backend ruff+pytest, contracts, frontend, docker. Earlier failures fixed: ruff E501/I001, stale contract schemas regenerated, a test that relied on a missing DB password env var made hermetic. actionlint passes |

Real end-to-end (25 Nov, real Postgres, sandbox, vite proxy, local Ollama): create, investigate, CONTEXT_RETRIEVED, DIAGNOSED, REVIEW_PENDING, approve/CLOSED (shop_api-001) and INCONCLUSIVE, reject/CLOSED (shop_api-017); audit complete; `lab/` and `datasets/` hashes unchanged. See `docs/demo/e2e-run.md`.

Not tested: PATCH_PROPOSED/VERIFIED and approve-with-patch-hash through the real path on any real provider (local 4B model gave malformed_edit; BeatAPI free returned 503; the strong-model run is owner-gated); the RC2 config-value checker inside the pipeline (standalone only); RC2 on unseen cases; `regression/` integrated into the pipeline; a clean-clone dry run. The frontend uses pnpm; the dev machine has only npm.

