# P3-S01 — Dataset scale-up and freeze

## A. Task identification
| Field | Value |
|---|---|
| Phase | 3 Dataset, evaluation and UI |
| Step | 1 |
| Task ID | P3-S01 |
| Synverk card | TRAC-19 |
| Primary owner | Muhammad Rafique |
| Supporting | Muhammad Ruhan Kamran (label peer check) |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Normal (critical path, largest task) |
| Effort | 4 days |
| Status | NEEDS REVIEW (test split frozen 22 Nov: 151 cases, sha256 881f2887…; D28 and peer check not done) |
| Branch | `rafique/P3-S01-dataset` |

## B. Objective
Produce the held-out evaluation set that satisfies rubric D1 (≥50 labelled examples per AI component) and gives graph retrieval a fair chance to matter, then freeze it so no tuning can touch it (safeguard 5).

## C. Prerequisites
- P1-S03 (generator, validator), P2-S02 (`distance()`).
- Read `docs/invariants/ml.md`.

## D. Technical background
- **Targets (held-out test):** ≥60 configuration, ≥60 application_code, ≥12 runtime_dependency, ≥12 insufficient_evidence (≥144). **Dev:** ≥30 from different `variant_group`s.
- **Coverage:** ≥10 fault families (config: wrong host, wrong port, renamed env var, wrong queue name, invalid type, Compose interpolation; code: empty-list index, off-by-one, swallowed exception, wrong serialization, retry boundary, worker state).
- **Distance:** ≥50% of test cases with computed distance ≥1, including all four patterns: config read in one module/failure in another; worker failing on an API-side setting; traceback ending in a library; bug in a caller of the crashing function.
- **Confusable pairs:** same visible symptom, different class (e.g. `connection refused` from wrong host vs stopped Redis).
- **Split by `variant_group`** so near-duplicates never cross dev/test.
- **Freeze:** after validation, write `datasets/manifests/test.sha256` (SHA-256 of `test.jsonl` plus hidden test files). The runner refuses unmatched test manifests (P3-S04).

## E. Implementation instructions
1. Extend templates and parameter tables to reach the family list; vary log wording, service, module, value.
2. Generate candidates into a staging manifest; compute `distance` with the graph for every case (`distance_source: "graph"`).
3. Assign splits by `variant_group` (deterministic seed); check counts, family balance and distance histogram; adjust generation until targets are met.
4. `task dataset:validate` on everything (red/green, hidden suite, leakage, runtime/insufficient behaviour, 3× flakiness).
5. **Peer check:** Ruhan reviews 10 random test cases (reads visible files + manifest, confirms the label makes sense) and comments on TRAC-19.
6. **Freeze:** `task dataset:freeze` writes the hash; commit manifests, cases, hidden tests and hash in one PR.
7. `task dataset:stats` prints counts by class/family/split/distance; paste on the card.

Edge cases: a variant that doesn't reproduce → drop it, never "fix" the label; families too easy (always distance 0) → add structural variants rather than rewording.

**Additions from the feasibility review (21 Nov 2026; see D18–D24)**
- Spread `log_format` across the test split (each format ≥15% of cases, including `none`) so results can be broken down by format (D24).
- Split by `variant_group`: all variants of one template stay in the same split, so test cases are never near-copies of dev cases.
- Ruhan writes or blind-reviews at least 25% of the fault templates before the graph is tuned, so faults aren't shaped around Rafique's own graph (Q12).

**Gap fixes (21 Nov 2026; see D26–D31)**
- Hidden tests use different inputs from visible tests for the same behaviour; the validator fails a case whose hidden test shares an input literal with its visible test (D31).
- The freeze record lists how many candidate cases the 3× flakiness check rejected (D27).

## F. Checklist
- [ ] ≥10 fault families implemented
- [ ] ≥60 config, ≥60 code, ≥12 runtime_dependency, ≥12 insufficient_evidence in test
- [ ] ≥30 dev cases, disjoint `variant_group`s
- [ ] Computed distance on every case; ≥50% test with distance ≥1
- [ ] Confusable pairs included
- [ ] Validator passes on every case
- [ ] Peer check of 10 cases commented by Ruhan
- [ ] Freeze hash written and committed
- [ ] Stats pasted on TRAC-19
- [ ] Log formats spread across the test split
- [ ] Split by variant_group verified
- [ ] ≥25% of templates written or reviewed by Ruhan
- [ ] Hidden inputs differ from visible inputs (validator check)
- [ ] Flaky-rejection count in the freeze record

## G. Expected deliverables
Modified/new: `datasets/generation/templates/*`, `datasets/cases/*`, `datasets/hidden_tests/*`, `datasets/manifests/{dev,test}.jsonl`, `datasets/manifests/test.sha256`, `Taskfile.yml` (`dataset:freeze`, `dataset:stats`).

## H. Testing and validation
- Validator green on all; stats meet every target; hash recomputes identically on Ruhan's laptop.
- Acceptance: no gold label text in any model-visible file (leakage scan).

## I. Dependencies and integration
- **Informed by:** P0-S06 limits report.
- **Depends on:** P1-S03, P2-S02.
- **Unblocks:** P4-S01 (test-split runs), P2-S03 weight tuning on dev, P5-S03.

## J. Definition of done
Merged after Ruhan's review; targets met; peer check done; freeze hash on `main`; TRAC-19 approved.
