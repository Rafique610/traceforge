# Final evaluation, stage 2 (RC1, AxForge key slot 2) and combined replicate-0 view

> **Correction note, 2026-11-25 (no result changed).** The correct replicate coverage of the whole RC1 evaluation in `results/final` is: replicate 0 on all **35** sites, replicate 1 on **12** sites, replicate 2 on **8** sites (23 sites have replicate 0 only). Earlier wording such as "12 sites with replicates 0 to 2" describes stage 1 only and over-states replicate 2 (8 of the 12 sites). This is a reduced evaluation, not the A3-protocol deliverable (L0 vs G0 on at least 50 cases); no claim that G1 or the graph arm is superior is established.

Date 24 Nov 2026. Same frozen RC1 code (fingerprint `ee3d8d87…`), pipeline v5, AxForge `glm-5.3-flash`, temperature 0, live requests, 30 s start-to-start pacing, halt on first failure. Run on **key slot 2** only. Extends [final-evaluation-report.md](final-evaluation-report.md) (stage 1: 12 cases, replicates 0 and 1, replicate 2 on 8 of them). Still a **staged, reduced evaluation**, not the full original protocol.

## What was added
- **Selection:** the 23 variant groups not covered by stage 1, one case each, drawn blind before any model call (`results/final/selection-stage2.json`, `random.Random(20261125)`). Stage 1 + stage 2 = all 35 variant groups of the frozen test split, one case per group. Composition of stage 2: 14 application code, 5 configuration, 2 insufficient-evidence, 2 runtime-dependency.
- **One replicate only** (replicate 0) for the new cases; stage 1 keeps its replicates (r1 on 12 sites, r2 on 8). The three-replicate requirement is therefore **still not met**: only 8 of the 35 sites have three replicates, 23 have one.
- **Conditions:** L0, G0, then L1/G1 as patch-stage runs from the shared, hash-verified diagnosis (`frozen-stage2-rep0.json`). Same `--final-rc1` guards (selection, fingerprint).
- **Execution:** 0 provider failures, 0 `provider_error` artifacts, no 429, no retries, no provider switch. Slot 2 ledger: 188 requests, 1,209,905 committed tokens (including a 31-token key probe). Combined AxForge committed 4,057,272 of the 4,800,000 internal ceiling (742,728 left).
- **Incident (setup, not provider):** the first launch stopped after 2 cases because evidence bundles had not yet been collected for the other 21 cases. They were collected locally (lab, no tokens) and the run resumed without repeating finished cases.

## Results, replicate 0, all 35 sites (`results/final/report-all35-r0/`)
| | L0 | G0 | L1 | G1 |
|---|---|---|---|---|
| diagnosis class correct | 32/35 | 35/35 | shared | shared |
| exact function/key, answerable (32) | 28/32 | 29/32 | shared | shared |
| fixed (verified, hidden pass) | 27/35 | 28/35 | 28/35 | 29/35 |
| visible-suite regressions | 0 | 0 | 0 | 0 |

By class (L0 / G0 fixed): code 20/20 and 20/20; configuration 7/9 and 8/9 (L1 8/9, G1 9/9); insufficient-evidence abstained 3/3 both arms; runtime-dependency class correct 1/3 (L) and 3/3 (G), no repair expected. Unsupported claims 0.

Stage 2 alone (23 sites): fixed L0 18, G0 18, L1 19, G1 19; class correct L0 22/23, G0 23/23.

## Feedback: the first real opportunity
In stage 1 no first attempt failed, so feedback was never exercised. In stage 2 it was, once per arm, on the configuration case `shop_api-020`: L0 and G0 used 3 attempts without feedback and ended REJECTED; L1 and G1 failed attempt 1, then received **visible-reproducer feedback** (test id and assertion excerpt, hashes recorded; `feedback_items` empty at attempt 1) and were verified at attempt 2. Attempt 1 changed `redis_host` to `lab_redis`, attempt 2 to `localhost`. By the pre-declared criterion: **feedback benefits 2 (one case, two arms), feedback harms 0.** This is one case; it is evidence that the mechanism can work, not an estimated effect. (Both L1 and G1 had the same shared diagnosis and arrived at the same case, so the two benefits are not independent.)

## Graph versus lexical (paired, same case)
Diagnosis exact function: both 28, G only 1, L only 0. Class correct: both 32, G only 3, L only 0 (the three class differences fall on configuration and runtime-dependency cases; per-case reasons are in `results/final/report-all35-r0/tables/`). Fixed F0: both 27, G only 1. Differences are one or three case-runs in 35 on single replicates; the replicate-to-replicate disagreement seen in stage 1 (same cases flipping between replicates) is of the same size, so **no claim of a graph advantage** is made. Token use does not separate the arms.

## Limitations added by stage 2
- One replicate for 23 sites; no variance estimate for them.
- The abstention and runtime-dependency strata remain small (3 and 3 sites).
- Feedback evidence: one case.
- Same model and provider throughout; slot 2 quota independence is owner-stated, not verified through the API.
- v4 comparison remains qualitative only (see the main report).
