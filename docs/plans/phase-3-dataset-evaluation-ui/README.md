# Phase 3 — Dataset, evaluation and product surface

**Status:** IN PROGRESS (status sync 2026-11-25: P3-S01 completed; Ruhan's P3-S03/S04 implemented and tested, not reviewed/approved)

## Phase information
- **Purpose:** turn the working pipeline into something that can be measured and shown: a frozen labelled dataset large enough for the rubric, metrics with a baseline, a reviewer UI, and an experiment runner with a results page.
- **Objectives:** ≥60 config + ≥60 code + ≥12 runtime_dependency + ≥12 insufficient_evidence held-out cases, ≥30 dev, ≥50% distance ≥1, frozen by hash; every metric computed from saved records; UI covering the full incident flow; resumable batch runs.
- **Scope:** no headline experiments yet (Phase 4), only dev-split runs to test the machinery.
- **Expected outcome:** milestone **M3**.
- **Prerequisites:** M2.

## Task overview
| Step ID | Task | Responsible | Dependencies | Status |
|---|---|---|---|---|
| [P3-S01](step-01-dataset-scale-up-and-freeze.md) | Dataset scale-up and freeze (TRAC-19) | Rafique | P1-S03, P2-S02 | COMPLETED (23 Nov) |
| [P3-S02](step-02-evaluation-metrics-and-baseline.md) | Metrics + rule baseline (TRAC-20) | Rafique | P0-S05 | IMPLEMENTED (per TWD) |
| [P3-S03](step-03-reviewer-ui.md) | Reviewer UI (TRAC-21) | Ruhan | P0-S03, P2-S05 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| [P3-S04](step-04-experiment-runner-and-results-page.md) | Experiment runner + results page (TRAC-22) | Ruhan | P2-S04 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |

## Execution order
- All four can run in parallel. P3-S02 has no real dependency beyond contracts, so Rafique can start it early (e.g. during Phase 2 if blocked).
- P3-S01 is the longest task in the project: start generating variants as soon as P2-S02's `distance()` exists.
- P3-S04's results page needs P3-S02's report JSON format; agree the format early (first day of the phase).
- **Blocking:** P3-S01's freeze blocks all test-split runs (P4-S01) and any weight/prompt tuning on test data.

## Deliverables
Frozen `datasets/manifests/test.jsonl` + `test.sha256`, `dev.jsonl`; metrics, rule baseline, failure export; reviewer UI pages; runner with condition files; results page.

## Completion criteria
- [ ] `task dataset:validate` passes on every case; counts and distance histogram meet targets; hash committed; peer check done
- [ ] `task eval:report` reproduces hand-computed metric examples; rule baseline scored on dev
- [ ] Full seed-case flow clickable in the UI; screenshots on TRAC-21
- [ ] A dev-split run completes, resumes after interruption, and the results page shows its real numbers

## Handoff to Phase 4
- Rafique → Ruhan: frozen hash; final metrics report schema.
- Ruhan → Rafique: dev-run records for a first look at failure modes.
- Both: demo flow candidates (which cases show the product best, chosen from dev, never cherry-picked from test results).

## Navigation
- [P3-S01 Dataset scale-up and freeze](step-01-dataset-scale-up-and-freeze.md)
- [P3-S02 Evaluation metrics and baseline](step-02-evaluation-metrics-and-baseline.md)
- [P3-S03 Reviewer UI](step-03-reviewer-ui.md)
- [P3-S04 Experiment runner and results page](step-04-experiment-runner-and-results-page.md)
- Previous: [Phase 2](../phase-2-evidence-to-repair/README.md) · Next: [Phase 4](../phase-4-a3-delivery/README.md) · [Plans README](../README.md)
