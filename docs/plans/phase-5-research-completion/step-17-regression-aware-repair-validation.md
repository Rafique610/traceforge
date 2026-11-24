# P5-S17 — Regression-aware repair validation (conditional, RC2)

Follow-up study **Root-cause and impact analysis** (added 2026-11-25, PROPOSED, pending owner approval Q18). Design: [root-cause-impact-regression-design.md](../../research/root-cause-impact-regression-design.md) sections 6.2, 6.3. Decision D37 (proposed). Changes `repair/`, therefore RC2 only.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 17 |
| Task ID | P5-S17 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Ruhan Kamran (existing repair-pipeline responsibility) |
| Supporting | Muhammad Rafique (impact/selection interface) |
| Reviewer | Muhammad Rafique |
| Priority | CONDITIONAL (see section C) |
| Effort | 3 days (ASSUMPTION, not measured) |
| Status | PARTIALLY COMPLETE (Ruhan-side layer IMPLEMENTED, TESTED, NOT INTEGRATED) |
| Branch | none (commit on `main`, D33) |

**Status sync 2026-11-25 (final).** Evidence: `backend/traceforge/regression/` (ImpactProvider protocol, sealed ImpactReport, default GraphImpactProvider over codeintel, deterministic select_tests, RegressionAwareRunner wrapping the repair runner without editing the frozen loop, PatchHistory JSONL, leak-guarded regression feedback, RetrievalAdapter registry, preregistration validator), 26 tests pass (real pytest temp repo); `docs/research/regression-validation-contract.md`. Not integrated into the pipeline (needs RC2 hooks in frozen files, Rafique's P5-S15 provider and a sandbox run_selected adapter); never run end-to-end with a real model. Five-fact detail: `docs/plans/RUHAN_TASK_TRACKER.md`.

## B. Objective
Add regression-aware validation to the repair loop: use the P5-S15 impact report and selected visible tests, keep the full visible suite and the single hidden gate, store every patch version with its results, and allow a controlled revision on visible regression evidence.

## C. Prerequisites (all required)
- Owner approval to start.
- P5-S10 (RC2) in place; this work yields a **new fingerprint**, never the frozen RC1.
- P5-S15 and P5-S16 show a benefit (offline thresholds passed). If not, drop.
- Any provider tokens need explicit owner approval; BeatAPI is dev-only.

## D. Technical background
- `repair/loop.py` already runs the whole visible suite every attempt, hidden gate once, `max_attempts` parameter (design section 1).
- Selection adds feedback and audit value, not extra visible-regression catches (section 6.2).
- Feedback precedent: visible-reproducer feedback used once in stage 2 on `shop_api-020` (section 6.3).

## E. Implementation instructions
1. In RC2 only: after the minimal patch (existing scope policy), build the impact report (P5-S15), run selected visible tests first, then the full visible suite, then the hidden gate once as today; reject on any failure.
2. Store every patch version with validation results and the impact report hash.
3. `max_attempts` configurable (today 3).
4. On a visible regression in a dependant, the next attempt may receive only the visible failing test id, assertion excerpt and the impact path. Hidden tests, hidden outputs and oracle data never enter any prompt or feedback (test).
5. Human approval unchanged; nothing deployed.
6. Compute and record the new RC2 fingerprint; do not alter RC1 files or its recorded fingerprint.

## F. Checklist
- [ ] Owner approval, P5-S10 and S15/S16 benefit evidence recorded
- [ ] Selected plus full visible tests; hidden gate once
- [ ] Patch versions stored with results and report hash
- [ ] Prompt/feedback leak test for hidden content
- [ ] New RC2 fingerprint; RC1 unchanged
- [ ] Token spend approved by owner (if any)

## G. Expected deliverables
RC2 repair changes, tests, stored per-attempt records, short result note.

## H. Testing and validation
- Unit: feedback builder includes only the permitted fields; hidden test id/output never present.
- Regression: with feature off, behaviour equals current RC2 baseline.
- Acceptance: owner-approved comparison design; results reported with CIs; unchanged human approval step.

## I. Dependencies and integration
- **Informed by:** design sections 6.2, 6.3.
- **Depends on:** P5-S10, P5-S15, P5-S16 (benefit shown); owner approval.
- **Unblocks:** none.

## J. Definition of done
Reviewed by Rafique; owner approved or dropped; frozen RC1 untouched.
