# A3 evidence and statistics (P4-S01 / P5-S03, feasible parts)

Facts only. Zero provider or model requests were made for anything in this note. Nothing under `results/final`, `datasets/**`, `runs/**` or the RC1-fingerprinted files was modified; no tuning on the test split (gold is used for scoring only).

## Provenance

| item | value |
|---|---|
| repo HEAD at analysis time | `64073ca3d72ddb70646c0b5da999055520832d5b` (it was `17ef0f4822daee36807845efbd8b72310676a68d`, the RC1 record `git_sha`, at the start of the session; the working tree has uncommitted changes) |
| `datasets/manifests/test.json` sha256 | `881f288763a8b32e15feab7fd6583a1a78baa05864e1736a77ca00a952ba603a` |
| dev / validation / freeze manifests sha256 | `c939167d...98d68f` / `ac5cb6eb...f585` / `7e83a2af...ee54` |
| RC1 code fingerprint | `ee3d8d873a6e939451650d031a919799138e621859f79bdd91994af3f6456b51` |
| hardware | AMD Ryzen 5 2600 (6 cores / 12 threads), 15.95 GB RAM, Windows 11 Pro 10.0.26200, Python 3.12, Docker Desktop (local sandbox) |
| seeds | bootstrap seed `20261125` (string-seeded `random.Random` per stratum/metric), 10,000 resamples, percentile 95%; `PYTHONHASHSEED=0` for E1; E1 itself is deterministic, weights untuned (`weights_tuned: false`) |

## Sample sizes against the supervisor's >= 50 requirement

| component | n | independent units | >= 50? |
|---|---|---|---|
| retrieval (L vs G), scored | 127 cases with a retrieval target (of 151) | 29 variant groups (20 application_code, 9 configuration); 24 cases / 6 groups are runtime_dependency or insufficient_evidence and have no retrieval target | cases yes; independent groups no (29) |
| rules diagnostic baseline | 151 cases | 35 groups | cases yes; groups no |
| LLM diagnosis (L0 / G0), RC1 | 35 sites (one case per group, replicate 0) | 35 | no |
| LLM repair (L0/G0/L1/G1), RC1 | 35 sites; only 29 are repairable (20 application_code, 9 configuration), 6 are runtime/insufficient with no patch target | 29 | no |

Cases inside a variant group are variants of one fault site and are not independent. Adding cases from the existing 35 groups would raise the case count without adding independent evidence. The frozen test split has only 35 groups, so independent n cannot exceed 35 without new groups, which would be a new dataset (not frozen, not covered by the RC1 fingerprint).

## 1. Retrieval, all 151 test cases (no LLM)

Outputs: `results/analysis/e1-test-all151/`. Evidence bundles for all 151 cases were collected locally with `lab_collect` (Docker lab, no tokens) into `evidence/` (151 bundles, no secret leak flagged, 0 errors; the 51 bundles already in `runs/evidence` were not reused for the final inputs, they were recollected into the new directory).

Two inputs, because they answer different questions:

- Plain collected evidence (`e1-test-all151`): the literal E1 module input. Test faults are mostly silent (HTTP 2xx, no trace frames), so L, G, R0 and trace_only all score about 0 (recall@10 L = G = 0.004). This is a property of the bundle, not of the rankers.
- Pipeline-v5 evidence (`e1-test-all151-v5symptom`): collected evidence plus the visible-test symptom and deterministic findings, built exactly as `real_run` v5 does before retrieval (script `scripts/analysis_symptom_evidence.py`; visible reproducer and visible suite only, no hidden suite, no gold). Checked on shop_api-008: the symptom/issue items are identical to the saved RC1 `evidence_v5.json`. 126 cases produced failing symptoms, 24 `no_failure` (counts from `symptom.log`; 1 further case was built in an earlier test run). This is the input the agent's retrieval actually sees, so it is the headline table.

Retrieval metrics, v5 evidence, n = 127 (R0 and trace_only recall@10 = 0.000; MRR 0.001 and 0.000):

| metric | L | G | G minus L | case-level 95% CI | group-clustered 95% CI (29 groups) | G better / L better / tie |
|---|---|---|---|---|---|---|
| recall@1 | 0.000 | 0.000 | 0.000 | [0, 0] | [0, 0] | 0 / 0 / 127 |
| recall@5 | 0.209 | 0.402 | +0.193 | [+0.126, +0.264] | [+0.083, +0.321] | 30 / 2 / 95 |
| recall@10 | 0.535 | 0.567 | +0.031 | [-0.016, +0.079] | [-0.035, +0.122] | 12 / 8 / 107 |
| MRR | 0.138 | 0.186 | +0.048 | [+0.029, +0.069] | [+0.011, +0.094] | 58 / 24 / 45 |
| nDCG@10 | 0.220 | 0.264 | +0.044 | [+0.019, +0.070] | [+0.004, +0.098] | 50 / 22 / 55 |

By cause class (G minus L; clustered CI):

| class (cases / groups) | recall@5 | recall@10 | MRR | nDCG@10 |
|---|---|---|---|---|
| application_code (67 / 20) | +0.313 [+0.145, +0.492] | +0.060 [-0.032, +0.197] | +0.075 [+0.027, +0.134] | +0.078 [+0.022, +0.159] |
| configuration (60 / 9) | +0.058 [-0.018, +0.184] | 0.000 [-0.083, +0.102] | +0.019 [-0.030, +0.083] | +0.006 [-0.039, +0.060] |

Reading: on this offline metric, G ranks gold nodes earlier than L for application_code (recall@5, MRR, nDCG@10 intervals exclude 0 even when clustered), the overall MRR and nDCG clustered lower bounds are close to 0 (+0.011, +0.004), and there is no difference at recall@10 or for configuration cases. Recall@1 is 0 for every method because the top-ranked hit is always the failing test node in these bundles. The sign-test p-values in `e1_bootstrap_*.md` treat cases as independent and are therefore too optimistic; use the clustered intervals. Only 9 configuration groups exist, so those intervals are wide. This is a retrieval-ranking result only; it does not show that graph retrieval improves diagnosis or repair (see section 3).

### Rules-based diagnostic baseline, 151 cases

No CLI exists for it (`runs/e2e/rules_baseline_report.json` was a smoke over a few cases); `scripts/analysis_e1_bootstrap.py` calls `traceforge.evaluation.baselines.rules.baseline_records` on all 151 bundles (identical results on plain and v5 evidence: the rules read only health/config/trace_frame items). Output: `rules_baseline_evidence.json`, `rules_baseline_evidence_v5.json`.

| measure | k / n | 95% Wilson (case) | 95% cluster bootstrap |
|---|---|---|---|
| cause-class accuracy, all | 14 / 151 (9.3%) | [5.6%, 15.0%] | [1.4%, 19.6%] |
| application_code | 0 / 67 | [0, 5.4%] | [0, 0] (degenerate) |
| configuration | 0 / 60 | [0, 6.0%] | [0, 0] (degenerate) |
| runtime_dependency | 2 / 12 | [4.7%, 44.8%] | [0, 50%] |
| insufficient_evidence | 12 / 12 | [75.8%, 100%] | [100%, 100%] |
| exact target (cases with a gold target) | 0 / 127 | [0, 2.9%] | [0, 0] (degenerate) |

Cause for the failures: the baseline abstains (`insufficient_evidence`) on 126 of the 127 application_code and configuration cases because the silent faults leave no connection error or trace frame.

## 2. RC1 final results, 35 sites (replicate 0), exact paired statistics

Source: `results/final/final-axforge-{L0,G0,L1,G1}/records` (read only). Script `scripts/analysis_rc1_stats.py` -> `results/analysis/rc1-paired-stats/`. "Fixed" = outcome `TEST_VERIFIED_IN_LAB`. The 6 non-repairable sites (3 runtime_dependency, 3 insufficient_evidence) are never fixed, so fixed-over-repairable is L0 27/29, G0 28/29, L1 28/29, G1 29/29.

| condition | fixed (35) | 95% Wilson | cause class correct | 95% Wilson | exact target | 95% Wilson |
|---|---|---|---|---|---|---|
| L0 | 27 | [61.0%, 87.9%] | 32 | [77.6%, 97.0%] | 28 | [64.1%, 90.0%] |
| G0 | 28 | [64.1%, 90.0%] | 35 | [90.1%, 100%] | 29 | [67.3%, 91.9%] |
| L1 | 28 | [64.1%, 90.0%] | 32 | (shared with L0) | 28 | |
| G1 | 29 | [67.3%, 91.9%] | 35 | (shared with G0) | 29 | |

Paired counts and exact two-sided McNemar (binomial on discordant pairs), n = 35 pairs each:

| comparison | measure | A only | B only | both | neither | discordant | exact p |
|---|---|---|---|---|---|---|---|
| L0 vs G0 (graph effect) | fixed | 0 | 1 | 27 | 7 | 1 | 1.000 |
| L0 vs G0 | cause class correct | 0 | 3 | 32 | 0 | 3 | 0.250 |
| L0 vs G0 | exact target | 0 | 1 | 28 | 6 | 1 | 1.000 |
| L1 vs G1 (graph effect, patch stage) | fixed | 0 | 1 | 28 | 6 | 1 | 1.000 |
| L0 vs L1 (feedback, linear retrieval) | fixed | 0 | 1 | 27 | 7 | 1 | 1.000 |
| G0 vs G1 (feedback, graph retrieval) | fixed | 0 | 1 | 28 | 6 | 1 | 1.000 |

None of these supports a superiority claim. Every fixed comparison has one discordant pair (p = 1.0); the cause-class difference has 3 discordant pairs (p = 0.25). The point estimates favour G and the feedback stage by one site each, which is within what one flipped site produces. L1/G1 are patch-stage runs from the shared L0/G0 diagnosis, so L0 vs L1 and G0 vs G1 differ only by the feedback patch stage, and L1 vs G1 differs only by the diagnosis (L vs G) carried over. The graph and feedback effects are not separable beyond that shared-diagnosis design.

Replicate noise (sites with replicates: 12 with r1, 8 of those also with r2; 55 case-runs per condition in total):

| condition | fixed on the 12 sites: r0 / r1 / r2 (r2 on 8) | sites whose fixed outcome differs across replicates |
|---|---|---|
| L0 | 9 / 10 / 6 | 1 (shop_api-019) |
| G0 | 10 / 10 / 6 | 0 |
| L1 | 9 / 10 / 6 | 1 (shop_api-019) |
| G1 | 10 / 10 / 6 | 0 |

Pooled 55 case-runs L0 vs G0 fixed: 43 vs 44, one discordant pair (not independent; reported only to show the noise level). Replicates show that the models' outcome is largely stable per site at temperature 0, so replicates do not add independent evidence either.

## 3. Why extending repair to >= 50 independent examples is blocked

Ledger arithmetic (`runs/axforge_usage.jsonl`, `runs/axforge_usage_k2.jsonl`, ceilings in `backend/traceforge/agent/axforge.py`: per-slot allowance 3,000,000; `COMBINED_CEILING` 4,800,000):

| quantity | tokens |
|---|---|
| slot 1 committed (2,812,447 reported + 34,920 estimated for failed requests) | 2,847,367 |
| slot 2 committed | 1,209,905 |
| combined committed | 4,057,272 |
| combined remaining to 4,800,000 | **742,728** |

Observed cost per RC1 site (record tokens in+out, replicate 0, 35 sites): L0 mean 22,341, G0 21,947, L1 3,202, G1 3,367. Diagnosis (L0+G0) about 44,289 per site; all four conditions mean 50,858 per site (median 41,612, p90 96,866). The 55 records per condition sum to 2.80M tokens, consistent with the ledger total.

| per-site cost assumption | max extra sites in 742,728 |
|---|---|
| mean 50,858 | 14 |
| median 41,612 | 17 |
| p90 96,866 | 7 |

Reaching 50 sites needs 15 more sites = about 762,866 tokens at the mean, more than the 742,728 remaining, before retries, error-estimate overhead (about 1.2% of slot 1) and any safety margin. A budget-limited run would at best reach 35 + 14 = 49, and the 35-group frozen test split has no further independent sites: the other 116 test cases are variants within the same 35 groups. Real independence requires new variant groups (new faults), not more cases per group. Of the extra sites, about 83% would also be repairable (29/35), so the repairable n would be lower still.

## Limitations

- Retrieval numbers come from untuned L/G weights on pipeline-v5 evidence reconstructed offline; they cover retrieval ranking only and do not transfer to diagnosis or repair accuracy.
- Group-clustered bootstrap with 29 (or 9, 20 per class) clusters is itself approximate; percentile intervals can be too narrow with few clusters. Degenerate rules-baseline intervals ([0, 0]) are an artefact of all-zero outcomes; use the Wilson bounds.
- Evidence bundles were recollected for this analysis, so they may differ in incidental fields (timestamps, ids) from the ones the RC1 runs used; the symptom items were checked equal on one site only.
- "Source localisation" is reported through the E1 node-level gold metrics (symbol or config key present in the top-k); no separate file-level metric exists in the module.
- 24 cases (runtime_dependency / insufficient_evidence) have no retrieval target and are excluded from retrieval scoring (127 of 151 scored).
- RC1 is a single model (glm-5.3-flash via AxForge), one case per group, with 6 of 35 sites non-repairable.

## Reproduce

```
# from d:\TraceForge\repo; PY=backend/.venv/Scripts/python.exe
cd backend
$PY -m traceforge.agent.lab_collect --manifest ../datasets/manifests/test.json --out ../results/analysis/e1-test-all151/evidence --jobs 3
cd ..
$PY scripts/analysis_symptom_evidence.py --manifest datasets/manifests/test.json --evidence-dir results/analysis/e1-test-all151/evidence --out results/analysis/e1-test-all151/evidence_v5 --jobs 3
cd backend
PYTHONHASHSEED=0 $PY -m traceforge.retrieval.e1 --manifest ../datasets/manifests/test.json --repo-root ../datasets/cases --evidence-dir ../results/analysis/e1-test-all151/evidence_v5 --out-dir ../results/analysis/e1-test-all151/e1 --run-id e1-test-all151-v5symptom
# (same with --evidence-dir .../evidence --run-id e1-test-all151 for the plain-bundle run)
cd ..
$PY scripts/analysis_e1_bootstrap.py e1-test-all151-v5symptom evidence_v5
$PY scripts/analysis_e1_bootstrap.py e1-test-all151 evidence
$PY scripts/analysis_rc1_stats.py
```

Files: `results/analysis/e1-test-all151/{e1_bootstrap_*.md,json, rules_baseline_*.json, e1/*/result.json}`, `results/analysis/rc1-paired-stats/{rc1_stats.json,rc1_stats.md}`.
