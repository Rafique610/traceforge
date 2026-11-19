# P4-S02 — Failure analysis and results presentation

## A. Task identification
| Field | Value |
|---|---|
| Phase | 4 Assignment 3 delivery |
| Step | 2 |
| Task ID | P4-S02 |
| Synverk card | TRAC-23 (part 2 of 3) |
| Primary owner | Muhammad Rafique |
| Supporting | Muhammad Ruhan Kamran (analyses for agent/repair failures) |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | High |
| Effort | 2 days |
| Status | NOT STARTED |
| Branch | `rafique/P4-S02-failure-analysis` |

## B. Objective
Turn raw results into what the examiners assess: ≥10 failure examples grouped by cause with planned fixes (rubric D4), an interpretation of each baseline difference (D3), and slides/results that every member can explain (E2, E3).

## C. Prerequisites
- P4-S01 results; P3-S02 failure export.

## D. Technical background
- Analyses use the taxonomy from P3-S02. Each member analyses failures from their own part: Rafique — retrieval/evidence/graph causes (`LOW_RETRIEVAL_RECALL`, `BAD_TRACE_MAPPING`, `MISBOUND_CONFIG_KEY`, `DYNAMIC_DISPATCH_NOT_RESOLVED`); Ruhan — agent/repair causes (`SIMILAR_SYMPTOM_WRONG_CAUSE`, `PATCH_FAILS_APPLY`, `TEST_OVERFIT`, `INSUFFICIENT_EVIDENCE_NO_ABSTENTION`, `COST_OR_TIMEOUT`).
- Interpretation must be honest: "graph didn't help at distance 0, helped at distance ≥1" or "no difference" are both acceptable findings.

## E. Implementation instructions
1. `task eval:failures RUNS=<L0>,<G0>` → `failures.csv`.
2. Each member fills `cause_category`, a 1–2 sentence explanation and a planned fix for at least 5 failures in their area (≥10 total; more if available), covering ≥4 categories.
3. `evaluation/results/a3/failure_analysis.md`: grouped table (category, count, example case IDs, explanation, planned fix, owner).
4. Slides (5–6): problem + architecture (1), dataset and distance histogram (1), E1 table (1), diagnosis LLM vs rules (1), L0 vs G0 repair + latency/cost (1), failure analysis + next steps (1). Every number copied from `report.json`; each slide footnotes the run IDs.
5. Each member rehearses explaining the other's slides (viva E3 is individual).

## F. Checklist
- [ ] Failure export generated
- [ ] ≥5 analyses by Rafique, ≥5 by Ruhan; ≥4 categories
- [ ] Planned fix and owner per category
- [ ] `failure_analysis.md` committed
- [ ] Slides built only from `report.json`
- [ ] Run IDs footnoted
- [ ] Cross-explanation rehearsal done

## G. Expected deliverables
`evaluation/results/a3/failure_analysis.md`, slides file (in the submission pack, outside or inside the repo per team choice).

## H. Testing and validation
- Spot-check 3 numbers on slides against `report.json` (reviewer does this).
- Acceptance: ≥10 analysed failures; every planned fix maps to a Phase 5/6 step or is explicitly deferred.

## I. Dependencies and integration
- **Depends on:** P4-S01.
- **Unblocks:** P4-S03; feeds P5-S01 and P6-S01.

## J. Definition of done
Analysis and slides reviewed by Ruhan; numbers verified; rehearsal done.
