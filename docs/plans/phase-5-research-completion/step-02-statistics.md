# P5-S02 — Statistics

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 2 |
| Task ID | P5-S02 |
| Synverk card | TRAC-25 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Low (A4) |
| Effort | 2 days |
| Status | NOT STARTED |
| Branch | `rafique/P5-S02-statistics` |

## B. Objective
Turn the 2×2 × 3 records into defensible claims: effect sizes with confidence intervals and paired tests, without treating repeated runs of the same case as independent evidence.

## C. Prerequisites
- P3-S02 metrics. Build and test on synthetic records with known answers; apply to P5-S03 output when ready. `numpy` (and optionally `scipy` for McNemar's exact test; decide by Ponytail ladder — exact binomial is a few lines).

## D. Technical background
- **Per-case outcome** for a condition = majority (or mean) of its 3 replicates; report both and say which is primary (**primary: mean success rate per case**).
- **Effects** on paired per-case values: graph main effect = mean(G0−L0, G1−L1); feedback main effect = mean(L1−L0, G1−G0); interaction = (G1−L1) − (G0−L0).
- **CIs:** paired bootstrap over **cases** (resample case IDs with replacement, 10,000 iterations, fixed seed), 95% percentile interval.
- **McNemar:** on binary per-case outcomes (majority vote) for each pair of conditions; exact binomial test on discordant pairs.
- **Breakdowns:** by `cause_class` and `distance` bucket, with n shown; no CIs claimed for n < 10 (report counts only).
- **Replicate variability:** per-case agreement across replicates (temperature 0 should be near-deterministic; report any disagreement).

## E. Implementation instructions
1. `evaluation/analysis/aggregate.py`: per-case per-condition outcome from replicates.
2. `evaluation/analysis/effects.py`: main effects and interaction.
3. `evaluation/analysis/bootstrap.py`: paired case-level bootstrap.
4. `evaluation/analysis/mcnemar.py`: exact test.
5. `task eval:stats RUNS=<dirs>` → `stats.json` + printed table.
6. Synthetic tests: construct records where the true effect is known (e.g. G always +1 on half the cases) and assert the estimates and CI coverage.

## F. Checklist
- [ ] Replicate aggregation (primary rule documented)
- [ ] Main effects and interaction
- [ ] Paired case-level bootstrap with fixed seed
- [ ] Exact McNemar
- [ ] Breakdowns with n; no CI for n < 10
- [ ] Replicate agreement report
- [ ] Synthetic-truth tests
- [ ] Applied to P5-S03 output; table on TRAC-25

## G. Expected deliverables
New: `backend/traceforge/evaluation/analysis/*.py`, tests, `stats.json` for the final runs.

## H. Testing and validation
- Synthetic tests recover known effects; CI contains the true value in a coverage simulation (e.g. ≥93% of 200 simulated datasets).
- Acceptance: running twice gives identical output (seeded).

## I. Dependencies and integration
- **Depends on:** P3-S02; final application needs P5-S03.
- **Unblocks:** P6-S03 comparison view, P6-S04 paper.

## J. Definition of done
Merged after Ruhan's review; synthetic tests pass; final stats computed from saved runs; TRAC-25 approved.
