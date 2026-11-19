# Phase 4 — Assignment 3 evaluation and delivery

**Status:** NOT STARTED

All three steps map to Synverk card **TRAC-23** (one card, three owners' activities; see contradiction X6 in [DECISIONS_AND_OPEN_QUESTIONS.md](../DECISIONS_AND_OPEN_QUESTIONS.md#contradictions-found)).

## Phase information
- **Purpose:** produce everything the Assignment 3 rubric checks during the live demo (stages C, D, E) from real, saved runs.
- **Objectives:** E1 retrieval on all cases; first R&D experiment (L0 vs G0 on ≥50 repairable test cases); rule baseline on all test cases; latency and cost; ≥10 failure analyses; results page and slides; demo script; submission pack; clean-clone dry run.
- **Scope:** Assignment 3 only. Full 2×2 is Phase 5.
- **Expected outcome:** milestone **M4**: demo-ready.
- **Prerequisites:** M3 (frozen data, metrics, UI, runner), P0-S04 approval, P2-S06 GitHub intake.

## Task overview
| Step ID | Task | Responsible | Dependencies | Status |
|---|---|---|---|---|
| [P4-S01](step-01-a3-experiments.md) | A3 experiments (TRAC-23) | Ruhan | P2-S07, P3-S01, P3-S02, P3-S04 | NOT STARTED |
| [P4-S02](step-02-failure-analysis-and-results.md) | Failure analysis and results (TRAC-23) | Rafique | P4-S01 | NOT STARTED |
| [P4-S03](step-03-demo-and-submission-pack.md) | Demo and submission pack (TRAC-23) | Ruhan | P0-S04, P2-S06, P3-S03, P4-S02 | NOT STARTED |

## Execution order
1. P4-S01 (runs take wall-clock time on the free tier; start right after the freeze). Rafique can run E1 and the rule baseline in parallel because they need no LLM.
2. P4-S02 once records exist (can start on partial results, finalize after all runs).
3. P4-S03 last; the dry run is the gate.

## Deliverables
Saved run directories and `report.json`; failure analysis table (≥10, grouped); 5–6 slides from real numbers; demo script; submission pack (proposal, approval, track declaration, repo link, AI-tool declaration, slides).

## Completion criteria
- [ ] E1 on all repairable test cases; per-distance table
- [ ] L0 and G0 on ≥50 repairable test cases; rule baseline on all ≥144
- [ ] Latency (median/P95) and cost per case reported
- [ ] ≥10 failure analyses grouped by cause with planned fixes
- [ ] Every number in slides/UI recomputes from saved runs
- [ ] Clean-clone dry run on the other member's laptop succeeds
- [ ] Submission pack complete

## Handoff to Phase 5
- The failure taxonomy and planned fixes become inputs to P5-S01 (graph improvements) and P6-S01 (hardening).
- Instructor feedback from the demo is logged in [DECISIONS_AND_OPEN_QUESTIONS.md](../DECISIONS_AND_OPEN_QUESTIONS.md).

## Navigation
- [P4-S01 A3 experiments](step-01-a3-experiments.md)
- [P4-S02 Failure analysis and results](step-02-failure-analysis-and-results.md)
- [P4-S03 Demo and submission pack](step-03-demo-and-submission-pack.md)
- Previous: [Phase 3](../phase-3-dataset-evaluation-ui/README.md) · Next: [Phase 5](../phase-5-research-completion/README.md) · [Plans README](../README.md)
