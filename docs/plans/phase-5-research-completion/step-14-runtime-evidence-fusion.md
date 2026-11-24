# P5-S14 — Runtime evidence fusion (Tier 2)

Follow-up study **Root-cause and impact analysis** (added 2026-11-25, PROPOSED, pending owner approval Q18). Design: [root-cause-impact-regression-design.md](../../research/root-cause-impact-regression-design.md) section 5 (evidence classes in section 3). Decision D37 (proposed). Zero tokens.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 14 |
| Task ID | P5-S14 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Tier 2 (only after the MVP shows a measurable gain) |
| Effort | 1.5 days (ASSUMPTION, not measured) |
| Status | NOT STARTED (proposed, pending owner approval) |
| Branch | none (commit on `main`, D33) |

## B. Objective
Turn runtime artifacts already visible to the model today (trace frames, log excerpts, failing visible test id) into `observed` marks on overlay nodes, used to re-rank and annotate candidates.

## C. Prerequisites
- P5-S12.
- Gate: MVP shows a gain.

## D. Technical background
- Observed facts re-rank and annotate; they **never create a `static` edge**. A fact that does not resolve to a file and symbol stays `unknown` (design section 5).
- Only `observed` relations may be described as having happened (section 3).
- Not planned: instrumenting target code or collecting call traces in the official pipeline.
- A **dev-only coverage run** on fixtures may build ground truth for the evaluation; it is never given to a model and never used at inference time.

## E. Implementation instructions
1. Parse trace frames (reuse `trace_map.py` behaviour read-only), log lines and the failing visible test id into `observed` marks: frame -> function; failing test -> covered functions.
2. Add observed-aware score terms to the P5-S12 ranker; priors fixed before evaluation.
3. Unresolvable facts become `unknown` marks, not edges.
4. Dev-only coverage oracle script under an evaluation path (not under the product package) that writes ground-truth labels for P5-S16 fixtures; never imported by pipeline code.
5. Never touch hidden tests or gold.

## F. Checklist
- [ ] Observed marks from frames, logs, failing test id
- [ ] Test: observed never creates a static edge
- [ ] Unresolved facts stay `unknown`
- [ ] Coverage oracle isolated, dev-only, not importable from pipeline code (test)
- [ ] RC1 fingerprint unchanged

## G. Expected deliverables
Overlay module additions, oracle script, tests.

## H. Testing and validation
- Unit: frame resolves to function; unresolvable frame -> `unknown`; edge counts of `static` class identical before/after observed fusion.
- Isolation: grep-style test that no pipeline module imports the oracle; no hidden-test path in marks.
- Acceptance: effect measured in P5-S16 scenarios A to C against preregistered thresholds.

## I. Dependencies and integration
- **Informed by:** design sections 3, 5.
- **Depends on:** P5-S12.
- **Unblocks:** P5-S16 full set; oracle labels for P5-S15/S16 evaluation.

## J. Definition of done
Reviewed by Ruhan; tests green; oracle output never reaches any prompt.
