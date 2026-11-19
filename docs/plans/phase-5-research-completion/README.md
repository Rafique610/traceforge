# Phase 5 — Research completion (Assignment 4)

**Status:** NOT STARTED

## Phase information
- **Purpose:** complete the research question with a full controlled experiment and proper statistics, plus the model-sensitivity study and an optional external check.
- **Objectives:** richer graph and harder faults; all four conditions × 3 replicates on the frozen test set; paired bootstrap CIs, McNemar and interaction; Devstral vs local Qwen comparison; optional BugsInPy subset reported separately.
- **Scope:** research and evaluation. Product hardening and the paper are Phase 6.
- **Expected outcome:** milestone **M5**.
- **Prerequisites:** M4 (A3 delivered); A3 failure analysis.

## Task overview
| Step ID | Task | Responsible | Dependencies | Status |
|---|---|---|---|---|
| [P5-S01](step-01-deeper-graph.md) | Deeper graph + new fault families (TRAC-24) | Rafique | P4-S03 | NOT STARTED |
| [P5-S02](step-02-statistics.md) | Statistics (TRAC-25) | Rafique | P4-S03 | NOT STARTED |
| [P5-S03](step-03-full-factorial-runs.md) | Full 2×2 × 3 runs (TRAC-28) | Ruhan | P4-S03 | NOT STARTED |
| [P5-S04](step-04-model-sensitivity.md) | Model sensitivity (TRAC-29) | Ruhan | P5-S03 (G1 runs) | NOT STARTED |
| [P5-S05](step-05-bugsinpy-subset.md) | BugsInPy subset, optional (TRAC-27) | Rafique | P4-S03 | NOT STARTED |

## Execution order
- **Decide first (both, half a day):** do P5-S01's graph changes go into the *main* experiment? If yes, P5-S03 waits for P5-S01 and all four conditions are re-run with the new graph (the frozen test set stays the same; new fault families go into a **separate** new held-out set). If no, P5-S03 starts immediately with the A3 graph. Record the decision as an ADR. Default recommendation: freeze the A3 graph for the main experiment; report P5-S01 as a follow-up analysis.
- P5-S02 builds on synthetic records and A3 results while P5-S03 runs (multi-day).
- P5-S04 after P5-S03's G1 runs exist (reuses the same contexts).
- P5-S05 is optional; drop first if time is short.

## Deliverables
New graph edges and fault families (+ new held-out set if used); 4 × 3 run directories; statistics module and tables; model comparison table; optional BugsInPy table.

## Completion criteria
- [ ] Graph decision ADR merged
- [ ] All 4 conditions × 3 replicates complete on the frozen test set (no missing cells)
- [ ] Graph main effect, feedback main effect and interaction with 95% paired bootstrap CIs; McNemar per pair
- [ ] Model comparison table with hardware notes
- [ ] Optional BugsInPy reported separately (or explicitly dropped)

## Handoff to Phase 6
Final numbers and tables for the paper (P6-S04) and the comparison view (P6-S03).

## Navigation
- [P5-S01 Deeper graph](step-01-deeper-graph.md)
- [P5-S02 Statistics](step-02-statistics.md)
- [P5-S03 Full factorial runs](step-03-full-factorial-runs.md)
- [P5-S04 Model sensitivity](step-04-model-sensitivity.md)
- [P5-S05 BugsInPy subset](step-05-bugsinpy-subset.md)
- Previous: [Phase 4](../phase-4-a3-delivery/README.md) · Next: [Phase 6](../phase-6-productization-paper/README.md) · [Plans README](../README.md)
