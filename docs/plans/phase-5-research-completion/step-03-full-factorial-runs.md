# P5-S03 — Full 2×2 × 3 factorial runs

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 3 |
| Task ID | P5-S03 |
| Synverk card | TRAC-28 |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | Muhammad Rafique (sandbox throughput) |
| Reviewer | Muhammad Rafique |
| Priority | Low (A4) |
| Effort | 3 days of work + multi-day unattended runs |
| Status | NOT STARTED |
| Branch | `ruhan/P5-S03-factorial-runs` |

## B. Objective
Run the complete controlled experiment that answers the research question: conditions L0, G0, L1, G1, three replicates each, on the frozen test set with the pinned model.

## C. Prerequisites
- A3 delivered; P3-S04 runner; graph decision ADR (phase README); ADR 0001 model still available (if not, ADR for the replacement and re-run everything — never mix models within the 2×2).

## D. Technical background
- **Volume:** ~120 repairable + 24 non-repairable cases × 4 conditions × 3 replicates ≈ 1,700 case runs. L0/G0 subset runs from A3 can be reused only if model, prompts, graph and code SHA are identical (check `meta.json`); otherwise re-run.
- **Replicates at temperature 0:** differences come from provider nondeterminism; replicates must bypass the cache (`cache=False` with a `replicate` field in the cache key) or they would be identical copies.
- **Throughput:** sandbox is the bottleneck; enable N parallel case workers (each with its own worktree and lab namespace via Compose project name `lab_<n>`), N chosen from P1-S02 timings and laptop RAM. Respect the provider RPS across workers.

## E. Implementation instructions
1. Add `replicate` to the runner and cache key; `cache=False` for replicates 2–3 on first run, cached after.
2. Add parallel workers with isolated Compose project names and worktrees; global rate limiter shared across workers.
3. Plan the schedule: estimate per-case time × 1,700 / N; spread over days within free-tier limits; run overnight.
4. Run L0, G0, L1, G1 × replicate 1..3; monitor; resume on failure.
5. Completeness check: `task eval:check-grid` asserts every case × condition × replicate exists.
6. Hand the run IDs to Rafique for P5-S02.

**Gap fixes (21 Nov 2026; see D26–D31)**
- Before starting, estimate total time = runs × (median model latency from P1-S05 probe + median sandbox time from P1-S02) and plan the run in resumable batches (D30).
- Check after replicate 2 that at least some records differ from replicate 1; if all are identical, report that the provider was deterministic and treat replicates as one (D26).

## F. Checklist
- [ ] Reuse-vs-rerun decision for A3 runs documented
- [ ] Replicate in cache key; first-run cache bypass
- [ ] Parallel workers with isolated labs
- [ ] Shared rate limiter
- [ ] Schedule estimated and posted on TRAC-28
- [ ] All 12 cells complete
- [ ] Grid completeness check passes
- [ ] Run IDs handed over
- [ ] Time estimate from measured medians
- [ ] Replicate-difference check recorded

## G. Expected deliverables
Run directories for 12 cells; `evaluation/results/a4/grid_meta.json` (committed); runner changes and tests.

## H. Testing and validation
- Parallel workers don't share lab state (test with two workers on different cases).
- Acceptance: completeness check passes; every record has the same model ID, prompt hashes and dataset SHA.

## I. Dependencies and integration
- **Depends on:** P4-S03, P3-S04, graph ADR.
- **Unblocks:** P5-S02 (final stats), P5-S04, P6-S04.

## J. Definition of done
Grid complete and consistent; runner changes merged after Rafique's review; TRAC-28 approved.
