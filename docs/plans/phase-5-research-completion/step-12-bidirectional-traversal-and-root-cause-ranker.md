# P5-S12 — Bidirectional traversal overlay and root-cause candidate ranker

Follow-up study **Root-cause and impact analysis** (added 2026-11-25, PROPOSED, pending owner approval Q18). Design: [root-cause-impact-regression-design.md](../../research/root-cause-impact-regression-design.md) sections 2, 3 (evidence classes), 8. Decision D37 (proposed); assumption AS12 (not used by this task). Zero tokens; frozen RC1 stays untouched.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 12 |
| Task ID | P5-S12 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | ESSENTIAL (MVP) |
| Effort | 3 days (inheritance/overrides edges about 1 d, traversal and ranker about 2 d; ASSUMPTION, not measured) |
| Status | IMPLEMENTED, TESTED; ranker preregistered NO-GO; not reviewed, not approved |
| Branch | none (commit on `main`, D33) |

**Status sync 2026-11-25.** Evidence: `backend/traceforge/analysis/` (overlay traversal and ranker); 41 analysis tests incl. S12/S15/S16. Rules R1, R2, R5 failed: on call chains the ranker equals graph distance; it helps on configuration and hub cases and abstains correctly on both static-blind cases. `docs/research/rootcause-impact-evaluation.md`. Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; the task stays Rafique's.

## B. Objective
Build an offline **overlay** on a copy of the existing code graph: inheritance and override edges, evidence classes (`static`, `observed`, `inferred`, `unknown`), budgeted bidirectional multi-hop traversal and a candidate ranker that returns ranked locations with an explanation path. It produces ranked hypotheses, not a claimed root cause.

## C. Prerequisites
- P5-S06 (benchmark harness and scorer) so the ranker is scored at equal token budget against RET-L and RET-G.
- Read-only knowledge of `codeintel/` (`queries.py`, `config.py` `REVERSE_OF`).

## D. Technical background
- Design section 3: depth default 2 for retrieval, 3 for impact; per direction, per edge type, node cap; top N frontier nodes per hop; test and file nodes stay leaves; stop at hubs unless the symptom names them.
- Evidence class mapping from today's data is mechanical (confidence and the `unknown:` prefix), so stored graphs need no change (design section 3).
- Score = seed relevance x path weight (edge-type prior x edge confidence x hub factor, decaying per hop). Priors are fixed before evaluation, not tuned on the test split (section 2).
- Inheritance: AST `ClassDef.bases` resolved to in-repo classes plus one import hop gives `inherits` and `overrides`; external bases are `unknown`. Protocol/ABC conformance without explicit bases is out of scope.
- **Never edit `codeintel/` or any RC1-fingerprinted file.** New code only, e.g. `backend/traceforge/analysis/`, working on a graph copy; not imported by any frozen file.

## E. Implementation instructions
1. Create `backend/traceforge/analysis/` (overlay, evidence classes, traversal, ranker). Load the graph, copy it, merge overlay edges into the copy.
2. Implement `inherits` / `overrides` edges with their reverses (`subclassed_by`, `overridden_by`) in the overlay only.
3. Implement evidence-class assignment per edge and per path (design section 3).
4. Implement budgeted traversal in both directions with configurable depth, node cap and per-hop top N; deterministic tie-breaking.
5. Implement the ranker; each candidate keeps its best path as a list of (edge type, provenance, evidence class, file:line). No model-written explanations.
6. Write the priors file and commit it before the first scored run. Wire the output to the P5-S06 harness as new arms; the same packer and budget as G.
7. Never read gold or hidden tests; never read `.env` values.

## F. Checklist
- [ ] Overlay merges into a copy; original graph object unchanged (test)
- [ ] `inherits` / `overrides` edges on fixtures
- [ ] Evidence classes assigned; `unknown:` targets stay `unknown`
- [ ] Traversal budgets respected; deterministic output
- [ ] Ranker returns explanation paths
- [ ] Priors committed before the first scored run
- [ ] RC1 fingerprint unchanged; no edits under `codeintel/`

## G. Expected deliverables
`backend/traceforge/analysis/` modules, priors file, unit tests, harness arm definitions.

## H. Testing and validation
- Unit: overlay does not mutate the source graph; inheritance resolution incl. external base -> `unknown`; cycle safety; node cap; hub stop; identical output on two runs.
- Hidden-test isolation: graph built from a worktree that excludes the hidden-test directory; test asserts no hidden path appears in any node or path.
- Acceptance: scored by P5-S16 (not decided here); 0 tokens; fingerprint unchanged.

## I. Dependencies and integration
- **Informed by:** design sections 2, 3, 8; retrieval-architecture-review.md.
- **Depends on:** P5-S06.
- **Unblocks:** P5-S13, P5-S14, P5-S16 (incrementally), P5-S15 (optional overlay input).

## J. Definition of done
Reviewed by Ruhan; tests green; fingerprint unchanged; limits stated (static analysis cannot see dynamic dispatch, reflection or framework magic; these stay `unknown`). No claim of complete root-cause coverage.
