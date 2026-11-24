# Phase 5 — Research completion (Assignment 4)

**Status:** IN PROGRESS (status sync 2026-11-25: P5-S03/S04 partial, P5-S10 implemented opt-in; S11 and S17 not started)

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
| [P5-S03](step-03-full-factorial-runs.md) | Full 2×2 × 3 runs (TRAC-28) | Ruhan | P4-S03 | PARTIALLY COMPLETE (reduced evaluation) |
| [P5-S04](step-04-model-sensitivity.md) | Model sensitivity (TRAC-29) | Ruhan | P5-S03 (G1 runs) | PARTIALLY COMPLETE (setup + monitor; no comparison) |
| [P5-S05](step-05-bugsinpy-subset.md) | BugsInPy subset, optional (TRAC-27) | Rafique | P4-S03 | NOT STARTED |
| [P5-S06](step-06-retrieval-benchmark-and-baselines.md) | Retrieval benchmark + baselines RET-L / RET-G, dev split (essential) | Rafique | P3-S01 (done), review of P2-S02/S03 | NOT STARTED |
| [P5-S07](step-07-incremental-index-and-embedding-cache.md) | Incremental chunk manifest, embedding cache, index verifier (essential) | Rafique | P5-S06 (data model in parallel) | NOT STARTED |
| [P5-S08](step-08-embedding-retrieval-and-fusion.md) | RET-E + fusion arms RET-LE/LG/LGE, ADR 0003 decision gate (essential) | Rafique | P5-S06, P5-S07 | NOT STARTED |
| [P5-S09](step-09-optional-reranking.md) | Optional reranking (optional) | Rafique | P5-S08 go | NOT STARTED |
| [P5-S10](step-10-rc2-pipeline-robustness.md) | RC2 candidate: pipeline robustness fixes (essential-optional, needs owner approval) | Ruhan | none (owner approval to start) | IMPLEMENTED opt-in, TESTED; NOT VALIDATED/APPROVED |
| [P5-S11](step-11-conditional-hybrid-experiment.md) | Conditional end-to-end hybrid experiment (conditional) | Ruhan (Rafique supports) | P5-S08 go (+P5-S10 if included) | NOT STARTED |
| [P5-S12](step-12-bidirectional-traversal-and-root-cause-ranker.md) | Bidirectional traversal overlay + root-cause ranker (essential, MVP) | Rafique | P5-S06 | NOT STARTED (proposed) |
| [P5-S13](step-13-config-value-flow-analysis.md) | Config value-flow analysis (Tier 2) | Rafique | P5-S12 (+MVP gain) | NOT STARTED (proposed) |
| [P5-S14](step-14-runtime-evidence-fusion.md) | Runtime evidence fusion (Tier 2) | Rafique | P5-S12 (+MVP gain) | NOT STARTED (proposed) |
| [P5-S15](step-15-change-impact-report-and-test-selection.md) | Change-impact report + visible-test selection (essential, MVP) | Rafique | P5-S06 (S12 optional) | NOT STARTED (proposed) |
| [P5-S16](step-16-root-cause-and-impact-evaluation-suite.md) | Root-cause and impact evaluation suite (essential, MVP reduced set) | Rafique (Ruhan verifies labels) | P5-S06; S12/S15 incrementally | NOT STARTED (proposed) |
| [P5-S17](step-17-regression-aware-repair-validation.md) | Regression-aware repair validation (conditional, RC2) | Ruhan (Rafique supports) | P5-S10, P5-S15, P5-S16 benefit, owner approval | NOT STARTED (proposed) |

## Execution order
- **Decide first (both, half a day):** do P5-S01's graph changes go into the *main* experiment? If yes, P5-S03 waits for P5-S01 and all four conditions are re-run with the new graph (the frozen test set stays the same; new fault families go into a **separate** new held-out set). If no, P5-S03 starts immediately with the A3 graph. Record the decision as an ADR. Default recommendation: freeze the A3 graph for the main experiment; report P5-S01 as a follow-up analysis.
- P5-S02 builds on synthetic records and A3 results while P5-S03 runs (multi-day).
- P5-S04 after P5-S03's G1 runs exist (reuses the same contexts).
- P5-S05 is optional; drop first if time is short.
- **Retrieval modernization study (added 24 Nov 2026, owner instruction; Rafique's Track A for retrieval, Ruhan for P5-S10/S11).** All offline, zero AxForge tokens for P5-S06 to P5-S09, dev split only, conditional on frozen RC1 (fingerprint `ee3d8d87...`) staying untouched (D36). Order: P5-S06 and the P5-S07 data model in parallel -> P5-S07 -> P5-S08 (decision gate, ADR 0003 PROPOSED) -> P5-S09 (optional) and P5-S11 (conditional, owner approval for any token spend). P5-S10 (RC2) runs independently once the owner approves. Design: [retrieval-architecture-review.md](../../research/retrieval-architecture-review.md). Design details are not repeated here.
- **Root-cause and impact analysis (added 25 Nov 2026, PROPOSED, pending owner approval Q18).** Offline, zero tokens, dev/fixture data only, frozen RC1 untouched (new modules, overlay on a graph copy). MVP: P5-S06 -> P5-S12 -> P5-S15 -> P5-S16 (reduced, 4 families x 3 cases). Tier 2, only after the MVP shows a measurable gain: P5-S13, P5-S14, full P5-S16 (8 x 5). Conditional: P5-S17 (RC2 only; owner approval, P5-S10, benefit shown by S15/S16). Design: [root-cause-impact-regression-design.md](../../research/root-cause-impact-regression-design.md). Capability is evaluated, not guaranteed; no claim of complete root-cause or impact coverage.

## Deliverables
New graph edges and fault families (+ new held-out set if used); 4 × 3 run directories; statistics module and tables; model comparison table; optional BugsInPy table; follow-up study: retrieval benchmark tables in `results/retrieval/`, incremental embedding index modules, ADR 0003 (PROPOSED), optional RC2 and hybrid experiment.

## Completion criteria
- [ ] Graph decision ADR merged
- [ ] All 4 conditions × 3 replicates complete on the frozen test set (no missing cells)
- [ ] Graph main effect, feedback main effect and interaction with 95% paired bootstrap CIs; McNemar per pair
- [ ] Model comparison table with hardware notes
- [ ] Optional BugsInPy reported separately (or explicitly dropped)
- [ ] Root-cause/impact study (proposed): MVP P5-S12, S15, S16-reduced decided by the owner; P5-S13, S14, S17 as approved or explicitly dropped
- [ ] Retrieval study: P5-S06 baselines and P5-S08 go/no-go ADR 0003 decided by the owner (P5-S07, S09, S10, S11 as approved or explicitly dropped)

## Handoff to Phase 6
Final numbers and tables for the paper (P6-S04) and the comparison view (P6-S03).

## Navigation
- [P5-S01 Deeper graph](step-01-deeper-graph.md)
- [P5-S02 Statistics](step-02-statistics.md)
- [P5-S03 Full factorial runs](step-03-full-factorial-runs.md)
- [P5-S04 Model sensitivity](step-04-model-sensitivity.md)
- [P5-S05 BugsInPy subset](step-05-bugsinpy-subset.md)
- [P5-S06 Retrieval benchmark and baselines](step-06-retrieval-benchmark-and-baselines.md)
- [P5-S07 Incremental index and embedding cache](step-07-incremental-index-and-embedding-cache.md)
- [P5-S08 Embedding retrieval and fusion, ADR 0003](step-08-embedding-retrieval-and-fusion.md)
- [P5-S09 Optional reranking](step-09-optional-reranking.md)
- [P5-S10 RC2 pipeline robustness](step-10-rc2-pipeline-robustness.md)
- [P5-S11 Conditional hybrid experiment](step-11-conditional-hybrid-experiment.md)
- [P5-S12 Bidirectional traversal and root-cause ranker](step-12-bidirectional-traversal-and-root-cause-ranker.md)
- [P5-S13 Config value-flow analysis](step-13-config-value-flow-analysis.md)
- [P5-S14 Runtime evidence fusion](step-14-runtime-evidence-fusion.md)
- [P5-S15 Change-impact report and test selection](step-15-change-impact-report-and-test-selection.md)
- [P5-S16 Root-cause and impact evaluation suite](step-16-root-cause-and-impact-evaluation-suite.md)
- [P5-S17 Regression-aware repair validation](step-17-regression-aware-repair-validation.md)
- Previous: [Phase 4](../phase-4-a3-delivery/README.md) · Next: [Phase 6](../phase-6-productization-paper/README.md) · [Plans README](../README.md)
