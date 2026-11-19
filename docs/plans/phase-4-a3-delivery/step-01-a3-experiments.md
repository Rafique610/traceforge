# P4-S01 — Assignment 3 experiments

## A. Task identification
| Field | Value |
|---|---|
| Phase | 4 Assignment 3 delivery |
| Step | 1 |
| Task ID | P4-S01 |
| Synverk card | TRAC-23 (part 1 of 3) |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | Muhammad Rafique (E1 and rule baseline runs) |
| Reviewer | Muhammad Rafique |
| Priority | High |
| Effort | 2 days (plus unattended run time) |
| Status | NOT STARTED |
| Branch | `ruhan/P4-S01-a3-experiments` |

## B. Objective
Produce the quantitative evidence for Assignment 3 stage D: test sets ≥50 per component (D1), metrics (D2), baselines (D3), latency/cost (D5) and the first R&D experiment (D6), all from saved, rerunnable runs on the frozen test split.

## C. Prerequisites
- P3-S01 frozen test set; P3-S02 metrics; P3-S04 runner; P2-S07 working pipeline.
- Free-tier limits known (ADR 0001).

## D. Technical background
- **Three experiments:**
  - **E1 retrieval** (no LLM): L vs G on all repairable test cases (≥120); Recall@5, MRR, nDCG@10, tokens, by distance.
  - **Diagnosis baseline:** rules vs LLM on all ≥144 test cases (LLM diagnosis comes from the L0/G0 runs for the ≥50 subset; rules on all).
  - **First R&D experiment:** L0 vs G0 (no feedback) on the same ≥50 repairable test cases (half config, half code; include distance ≥1 cases proportionally), pinned model, temperature 0.
- **Subset choice:** the ≥50 cases are chosen by a fixed seed from the frozen manifest **before** any run, and the list is committed; never chosen after seeing results.
- Paired per-case differences are reported (P3-S02 helper); full CIs come in P5-S02.

## E. Implementation instructions
1. `task eval:subset SPLIT=test N=50 SEED=<fixed>` → `evaluation/subsets/a3_subset.txt` (committed).
2. Rafique runs `task eval:retrieval SPLIT=test` and `task eval:baseline SPLIT=test`; saves outputs.
3. Ruhan runs `task eval:run SPLIT=test CONDITION=L0 SUBSET=a3_subset` then `CONDITION=G0`; monitor rate limits; resume as needed.
4. `task eval:report RUNS=<L0>,<G0>,<RULES>,<E1>` → `report.json`.
5. Export a copy of `report.json` and run metadata to `evaluation/results/a3/` (committed; small, no raw prompts).
6. Paste the headline tables on TRAC-23 with run IDs.

## F. Checklist
- [ ] Subset fixed by seed and committed before runs
- [ ] E1 on all repairable test cases
- [ ] Rule baseline on all test cases
- [ ] L0 run complete on subset
- [ ] G0 run complete on subset
- [ ] Report built; results exported and committed
- [ ] Latency median/P95 and cost per case in report
- [ ] Tables + run IDs on TRAC-23

## G. Expected deliverables
`evaluation/subsets/a3_subset.txt`, `evaluation/results/a3/report.json` + meta; run directories (local, git-ignored).

## H. Testing and validation
- Rerun `task eval:report` from the saved runs on Rafique's laptop → identical numbers.
- Rerun one condition from cache → identical records, zero API calls.
- Acceptance: each component's n ≥ 50; denominators shown.

## I. Dependencies and integration
- **Depends on:** P2-S07, P3-S01, P3-S02, P3-S04.
- **Unblocks:** P4-S02.

## J. Definition of done
Results committed and reproducible on both laptops; TRAC-23 updated with tables and run IDs; reviewed by Rafique.
