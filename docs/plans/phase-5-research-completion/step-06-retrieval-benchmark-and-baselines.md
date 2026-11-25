# P5-S06 — Retrieval benchmark harness and baselines (RET-L, RET-G)

Follow-up study **Retrieval modernization** (added 2026-11-24 at the project owner's instruction). Design: [retrieval-architecture-review.md](../../research/retrieval-architecture-review.md) sections 0, 5, 7. Decision D36. Everything is **conditional on frozen RC1 staying untouched** and costs **zero AxForge tokens**.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 6 |
| Task ID | P5-S06 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | ESSENTIAL (for this study) |
| Effort | 1.5 days (design doc: 1 to 1.5) |
| Status | IMPLEMENTED, TESTED (25 tests); not reviewed, not approved |
| Branch | none (commit on `main`, D33) |

**Status sync 2026-11-25.** Evidence: `backend/traceforge/retrieval_bench/`, `benchmarks/retrieval/` (itsdangerous 2.2.0 small, requests v2.32.3 medium, this repo's `lab/` complex; 45 queries, 98 gold units; labels Claude-authored, second check pending via `second_review.csv`), `docs/research/retrieval-benchmark-baselines.md`. Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; the task stays Rafique's.

## B. Objective
An offline, reproducible benchmark that scores the existing arms RET-L (= current L) and RET-G (= current G) on the **dev split** (33 cases), so every later arm (P5-S08) is compared against measured baselines at an equal token budget. Gold labels are used by the scorer only.

## C. Prerequisites
- P3-S01 frozen dataset (COMPLETED: dev 33, test 151). The test split and the 35 analysed sites are never used.
- Rafique's review of P2-S02 / P2-S03 (existing handoff items; their status is not changed here). The harness consumes that code as-is.
- Saved evidence bundles for the dev cases; E1 skips cases without one, so collecting missing bundles (needs the faulty lab and Docker) is part of this step.

## D. Technical background
- Existing harness: `backend/traceforge/retrieval/e1.py` (`task eval:retrieval SPLIT=dev`) and `evaluation/metrics/retrieval.py`. `e1.py`, `baselines.py`, `compare.py` and `codeintel/*` are outside the RC1 fingerprint list, but `codeintel/` and the frozen retrieval files are treated as **de facto frozen** (review section 6.1): do not edit them.
- Metrics, protocol and contamination controls are specified in review section 5; this step implements items 1 to 3 and 5 and does not run any fused or dense arm.
- Per-arm latency is not recorded in saved artifacts; the harness records it itself (outside the fingerprinted path).

## E. Implementation instructions
1. New harness code only in new files (under `backend/traceforge/retrieval/` or a new feature folder `retrieval_bench/`), none imported by a frozen file, each <= ~300 lines.
2. Load dev manifest and bundles; run RET-L and RET-G through the existing `retrieve()` at 3000 tokens (2400 usable).
3. Compute Recall@K, Precision@K, MRR (K = 1, 5, 10 and "in packed context"), nDCG@10, source-localization (gold file/symbol at rank 1), evidence coverage (gold config key / runtime artifact in bundle), context tokens (chars/4), build and query latency.
4. Paired per-case bootstrap 95% CIs (10,000 resamples, fixed seed) for any two-arm difference; sign test as secondary; per cause class (configuration, application_code); runtime_dependency and insufficient_evidence (n = 1 each) listed, not analysed.
5. Equal-token-budget protocol and budget-matched baselines (L and G with budget raised to a target token count) built into the CLI so P5-S08 reuses them.
6. Write `results/retrieval/<run_id>/` (rows, summary, `run_meta`: arm, split hash, seed, package versions, fingerprint before and after). Never write to `results/final`.
7. Add a `task` target (or document the module command) and a README line.

## F. Checklist
- [ ] Dev bundles inventory: which of the 33 have bundles, which were collected, which are skipped (with reason)
- [ ] RET-L and RET-G scored with all metrics above
- [ ] Bootstrap CIs and sign test implemented and unit-tested on hand-computed data
- [ ] Equal-budget and budget-matched modes
- [ ] Latency recorded per arm outside the fingerprinted path
- [ ] Two runs give identical rankings
- [ ] `code_fingerprint()` equals `ee3d8d87...` before and after; no file under `results/final` changed
- [ ] README and TESTING_AND_VALIDATION row updated

## G. Expected deliverables
Harness module(s) and CLI; `results/retrieval/<run_id>/` baseline tables; a short results note (numbers only from the saved run).

## H. Testing and validation
- Unit: metrics vs hand-computed values; bootstrap with a fixed seed reproduces; `GraphFeatures` all off equals L (existing fairness test still passes).
- Determinism: two consecutive runs produce byte-identical ranking files.
- Leakage: a test asserts no `hidden_tests`, `mutation.patch`, gold manifest or faultgen artifact path is in any indexed chunk.
- Acceptance: baselines reported for every dev case that has a bundle; skipped cases listed; fingerprint unchanged; 0 tokens spent.

## I. Dependencies and integration
- **Informed by:** retrieval-architecture-review.md; technical-findings-2026-11-24.md section 3.
- **Depends on:** P3-S01 (COMPLETED); Rafique's review of P2-S02 / P2-S03.
- **Runs in parallel with:** the data-model part of P5-S07.
- **Unblocks:** P5-S08 (needs the baselines and the scorer), P5-S09.

## J. Definition of done
Baseline tables saved and reviewed by Ruhan; acceptance checks above pass; status set to NEEDS REVIEW with the check output; only the owner approves.
