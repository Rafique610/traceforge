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
