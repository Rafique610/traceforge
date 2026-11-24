# Final controlled evaluation: consolidated execution plan (NOT STARTED; needs the owner's approval)

Written 24 Nov 2026. Release candidate RC1 is frozen; nothing below has been run. The frozen test split has not been used in any development, tuning or validation step.

## 1. Release candidate RC1
- Code: pipeline v5 (dev-d1 lineage) plus the milestone-1 improvements (diagnostics findings, symptom-config anchors, feedback provenance + guard v2, hash-bound approval hardening, request hygiene). Code fingerprint (28 behaviour files, recorded in every run's metadata): `c74da59757506256baa56b38d66808e89a9848414c56b51295882bd55d796b35`.
- Verified: backend 916 passed / 21 skipped (the skips are live-Docker/e2e tests), Ruff clean; frontend 69 tests, typecheck, build; Alembic upgrade/check/downgrade/upgrade on a clean Postgres, API container migrates on start (found and fixed: it did not before); prod compose builds and runs healthy; API write workflows verified on Postgres (redaction, hash-chained audit events, 404/422/409); request ids, 1 MB cap, generic 500s.
- Pre-freeze model check (dev split, 3 configuration sites, L0, ~92k tokens): diagnosis named the right key 3/3 (one differing only in letter case, fixed by v5 key canonicalisation); patches verified 2/3. The failure (low_stock_level) is a real feedback opportunity: all three F0 attempts wrote the same wrong value (2, needs >= 3), so F1 is exercised by a genuine case.
- Known limitations: Level-1/config results so far are dev-split, one sample; the symptom exposes function names through visible test names; the API has no endpoint that runs the agent (runs come from the CLI and are reviewed in the UI; deliberate, to keep provider spending out of the API); the Dashboard issues about 14 requests per load; hidden-suite regressions are reported as counts only; no v4 vs v5 paired diagnosis comparison exists.

## 2. The scale problem (consequential; the formal design does not fit the budget)
Formal design: 151 test cases x 4 conditions x 3 replicates = 1,812 case-runs. Measured v5 costs per (arm, case): code fault about 17k tokens (diagnosis about 13k + one patch request about 4k), configuration fault about 25k (one dev case with three failed attempts cost 61k), non-repair (abstain/runtime) about 8k. Even sharing the diagnosis between L0/L1 and G0/G1 (feedback only matters after a failed first patch), one replicate of all 151 cases is about 6M tokens and the full design about 36M. **Left to the 2.4M ceiling: 1,144,714** (1,255,286 committed; the 600k reserve lies beyond the ceiling and stays untouched). The full design is therefore about 30x over budget. Any run that fits is a deliberate reduction of the formal protocol, which needs the owner's explicit approval.

## 3. Options
- **A (recommended): a pre-registered stratified subset of the frozen test split, 1 replicate, all 4 conditions.** 18 cases, one per variant group, drawn with a recorded seed before any run: 8 of the 20 code groups, 6 of the 9 configuration groups, 2 of the 3 abstention groups, 2 of the 3 runtime groups (variants of a group are near-duplicates, so groups are the sampling unit). Design per case: diagnose once per arm (L and G), patch attempt 1 once per arm, and only when attempt 1 fails run attempts 2 and 3 in two branches (F0 without feedback, F1 with visible-test feedback). L0/L1 share the L diagnosis and G0/G1 share the G diagnosis (the feedback factor acts only inside the patch loop, so this is identical to running four independent conditions up to the first patch; the shared parts are reported as shared, not as independent replicates).
- **B: wait for the AxForge allowance window to reset.** The allowance is described as 3M tokens per 30 days; the ledger began 22 Nov. If the owner confirms on the dashboard when it resets, the ceiling logic permits a second block of up to 2.4M tokens: about 40 cases or two replicates of about 18 cases. This needs the owner's dashboard check and a decision on how the ledger treats the new window (the ledger and reserve rules are currently cumulative; changing that is a policy change).
- **C: BeatAPI replicates as a separate, non-formal experiment** (free, about 1 request per 90 s, different model variant): extra samples and breadth, never mixed into the formal comparison; this is the already-approved cross-provider design.
- **D: the full design.** Not feasible within the budget.

## 4. Option A in numbers
| Item | Estimate |
|---|---|
| Cases / conditions / replicates | 18 / L0, G0, L1, G1 / 1 (the formal requirement of 3 replicates is NOT met; reported as such) |
| Provider and model | AxForge `glm-5.3-flash` for every condition (no provider mixing); temperature 0; live requests; 30 s shared pacing; halt on first failure/429 |
| Tokens: first attempts | code 8 groups x 2 arms x 17k = 272k; configuration 6 x 2 x 25k = 300k; abstain/runtime 4 x 2 x 8k = 64k |
| Tokens: feedback branches | about 25% of repairable (arm, case) units fail attempt 1: about 7 units x 2 branches x 8k = about 112k |
| **Total expected** | **about 750k (range 550k to 1.0M)**; headroom after: about 395k expected, 145k worst case, to the 2.4M ceiling; the 600k reserve untouched |
| Requests / duration | about 120 to 140 live requests; at least 70 minutes of mandatory pacing; realistically 2 to 3 hours including model latency and about 15 s of sandbox per attempt; evidence collection for the 18 selected cases (Docker, no tokens) about 10 to 15 minutes beforehand |
| Safeguards | 700k floor (refuse to start below it) is raised to a 350k floor for this plan; ledger verified before each run; hidden suite once per final patch, counts only; leak guard v2 on every request; frozen manifest of inputs; run ids `final-axforge-...`, tier `formal-rc1`, separate from `results/development`; code fingerprint in every record |

## 5. What will be reported
Per condition and per stratum: diagnosis class/file/function accuracy, abstention rate (and correct abstentions), patch generated/applied, reproducer, visible and hidden pass, regressions, tokens and latency; paired L-vs-G (retrieval) and F0-vs-F1 (feedback) comparisons at case level with explicit counts (no significance claims at n = 18), failure taxonomy, the retrieval records (L, G, overlap, unique hits), graphs/tables, and a plain statement of what the evidence supports and what it does not (one replicate, 18 cases, one model, identifier exposure through visible test names).

## 6. Historical results
All dev-d1 and earlier results (patch_v3, patch_v4, pilots, screening, dev-d1 diagnosis/patch/config runs) are development or historical: none was produced by RC1 and none is reused in the formal comparison. They stay on disk with their provenance.

## 7. Decisions needed before anything runs
1. Approve option A (or B/C/another) knowing it is a **reduction of the formal protocol**: 18 cases instead of 151 and 1 replicate instead of 3.
2. Approve **pipeline v5 (RC1) as the formal pipeline** for this evaluation (v4 remains the historical formal pipeline).
3. If B: check the AxForge dashboard for the allowance reset date and decide how the cumulative ledger/reserve rules apply to a new window.
4. Approve reading the frozen test split's case metadata and collecting live-lab evidence for the 18 selected cases (no tokens); the draw and the case list are frozen in a file before the first model call.
