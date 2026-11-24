# Failure analysis: non-verified case-runs (final-axforge L0/G0/L1/G1)

> **Correction note, 2026-11-25 (no result changed).** The correct replicate coverage of the whole RC1 evaluation in `results/final` is: replicate 0 on all **35** sites, replicate 1 on **12** sites, replicate 2 on **8** sites (23 sites have replicate 0 only). Earlier wording such as "12 sites with replicates 0 to 2" describes stage 1 only and over-states replicate 2 (8 of the 12 sites). This is a reduced evaluation, not the A3-protocol deliverable (L0 vs G0 on at least 50 cases); no claim that G1 or the graph arm is superior is established.

Sources: `results/final/final-axforge-{L0,G0,L1,G1}/records/*.json` and `cases/<case>.r<k>/{diagnosis,repair,run_meta,trace,requests.jsonl,patch.diff}`; gold from `datasets/manifests/test.json`. Row-level data: `results/analysis/failure_cases.csv` (44 rows, one per non-verified case-run). No model or network calls were made.

## 1. Findings summary

- 220 case-runs (55 per condition = 35 cases + 12 stage-1 r1 + 8 stage-1 r2). 176 are `TEST_VERIFIED_IN_LAB`; **44 are not**.
- **40 of the 44 are expected non-repairable** (manifest `cause_class` insufficient_evidence or runtime_dependency). Correction to the earlier "5 per replicate": it is **6 of 35 cases (3 insufficient_evidence: shop_api-102, -028, -060; 3 runtime_dependency: shop_api-030, -134, -026)**. 102 and 030 are stage 1 (r0-r2 = 3 case-runs each); 028, 060, 134, 026 are stage 2 (r0 only) -> 10 case-runs per condition.
- **4 are genuine repair failures out of 180 repairable case-runs (97.8% verified)**: L0 2, G0 1, L1 1, G1 0. They involve only two stage-2 configuration cases, r0: shop_api-019 and shop_api-020.
- Diagnosis class-correct but no verified fix: 34 case-runs, of which 32 are correct abstentions / no-patch on non-repairable cases (expected) and **2 are genuine** (shop_api-020 L0 and G0: class `configuration` and key `shop_api.REDIS_HOST` match gold, patch value wrong).
- Of the 40 non-repairable case-runs, 8 diagnoses were not class-correct: 6 where no diagnosis was ever submitted (shop_api-030, `failure_reason=model_output_malformed`) and 2 where the model abstained with insufficient_evidence on a runtime_dependency case (shop_api-134 in L0 and L1). Outcome is the same (no patch).
- Feedback (F0 -> F1): `diagnosis` in every L1 record equals the L0 record (and G1 equals G0; all 55 cases checked), so feedback acts only on the patch loop. shop_api-020 fails in L0 and G0 but is verified in L1 and G1: feedback fixed it. shop_api-019 L1 fails because it inherits the L0 diagnosis failure (patch loop never reached).
- L vs G: shop_api-019 fails in L0/L1 but is verified in G0/G1; shop_api-134 is diagnosed runtime_dependency in G0/G1 but abstained in L0/L1; shop_api-030 malformed diagnosis in L on r0 and r2, in G on r1. Samples are tiny; no causal claim about retrieval is made (section 8).

## 2. Counts by category and condition

| Category | Root-cause stage | L0 | G0 | L1 | G1 | Total |
|---|---|---|---|---|---|---|
| Non-repairable, correct-class abstention / no patch (expected) | inherent | 7 | 9 | 7 | 9 | 32 |
| Non-repairable, diagnosis never submitted (030, rationale >500 chars rejected twice) | inherent (secondary: provider/model output) | 2 | 1 | 2 | 1 | 6 |
| Non-repairable, wrong class: insufficient_evidence vs runtime_dependency (134) | inherent (secondary: diagnosis) | 1 | 0 | 1 | 0 | 2 |
| **Genuine**: right key, wrong value, 3 identical attempts (020) | patch generation | 1 | 1 | 0 | 0 | 2 |
| **Genuine**: invalid diagnosis output, rationale >500 chars (019) | provider/model output | 1 | 0 | 1 | 0 | 2 |
| **Total non-verified** | | 12 | 11 | 11 | 10 | 44 |
| of which genuine | | 2 | 1 | 1 | 0 | 4 |
| Repairable case-runs (denominator) | | 45 | 45 | 45 | 45 | 180 |

No row is classified retrieval, patch policy (scope/guard) or validation: none of the 44 has a scope/guard/validation rejection (`attempts[].reasons` is `[]` for all genuine attempts, `rejection_text` null, `sandbox_detail` null; `repair.outcome` is REJECTED only for `visible_failed` on 020).

## 3. Ranked improvement opportunities (by case-run count)

1. **Diagnosis-output schema failures: 8 case-runs** (6 on non-repairable 030 + 2 genuine on 019). Same artifact signature: `trace.json` shows `submit_diagnosis` rejected twice with `string_too_long`, `loc: ('rationale',)`, `String should have at most 500 characters`; run ends `abstained:invalid_output` or `abstained:model_output_malformed`. Only the 2 on 019 cost a repairable case-run (L0, L1). G0 019 hit the same rejection once and then succeeded (`trace.json`: one rejected then `submit_diagnosis ok:true`).
2. **Patch loop repeats an identical edit without feedback: 2 genuine case-runs** (020 L0, G0). Edit is in the gold file/line (settings.py line 20) but sets `"lab_redis"`; attempts 1-3 have identical `edit_summary`; with feedback (L1/G1) attempt 2 became `"localhost"` and verified.
3. Class-wrong abstention on runtime_dependency (134, L only): 2 case-runs, no outcome impact.
4. Everything else (32) is expected behaviour.

## 4. Non-repairable case-runs (expected; separate from genuine failures)

Manifest `cause_class`: shop_api-102, -028, -060 = insufficient_evidence; shop_api-030, -134, -026 = runtime_dependency.

| Case | Cond (replicates) | Diagnosis (records `diagnosis.cause_class`) | failure_reason / failure_category |
|---|---|---|---|
| shop_api-026 | G0 (r0) | r0: runtime_dependency | record.failure_reason=None / run_meta.failure_category=no_patch |
| shop_api-026 | G1 (r0) | r0: runtime_dependency | record.failure_reason=None / run_meta.failure_category=no_patch |
| shop_api-026 | L0 (r0) | r0: runtime_dependency | record.failure_reason=None / run_meta.failure_category=no_patch |
| shop_api-026 | L1 (r0) | r0: runtime_dependency | record.failure_reason=None / run_meta.failure_category=no_patch |
| shop_api-028 | G0 (r0) | r0: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-028 | G1 (r0) | r0: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-028 | L0 (r0) | r0: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-028 | L1 (r0) | r0: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-030 | G0 (r0,r1,r2) | r0: runtime_dependency; r1: insufficient_evidence (abstained); r2: runtime_dependency | record.failure_reason=None / run_meta.failure_category=no_patch; record.failure_reason=model_output_malformed / run_meta.failure_category=abstained:model_output_malformed |
| shop_api-030 | G1 (r0,r1,r2) | r0: runtime_dependency; r1: insufficient_evidence (abstained); r2: runtime_dependency | record.failure_reason=None / run_meta.failure_category=no_patch; record.failure_reason=model_output_malformed / run_meta.failure_category=abstained:model_output_malformed |
| shop_api-030 | L0 (r0,r1,r2) | r0: insufficient_evidence (abstained); r1: runtime_dependency; r2: insufficient_evidence (abstained) | record.failure_reason=None / run_meta.failure_category=no_patch; record.failure_reason=model_output_malformed / run_meta.failure_category=abstained:model_output_malformed |
| shop_api-030 | L1 (r0,r1,r2) | r0: insufficient_evidence (abstained); r1: runtime_dependency; r2: insufficient_evidence (abstained) | record.failure_reason=None / run_meta.failure_category=no_patch; record.failure_reason=model_output_malformed / run_meta.failure_category=abstained:model_output_malformed |
| shop_api-060 | G0 (r0) | r0: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-060 | G1 (r0) | r0: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-060 | L0 (r0) | r0: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-060 | L1 (r0) | r0: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-102 | G0 (r0,r1,r2) | r0: insufficient_evidence (abstained); r1: insufficient_evidence (abstained); r2: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-102 | G1 (r0,r1,r2) | r0: insufficient_evidence (abstained); r1: insufficient_evidence (abstained); r2: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-102 | L0 (r0,r1,r2) | r0: insufficient_evidence (abstained); r1: insufficient_evidence (abstained); r2: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-102 | L1 (r0,r1,r2) | r0: insufficient_evidence (abstained); r1: insufficient_evidence (abstained); r2: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-134 | G0 (r0) | r0: runtime_dependency | record.failure_reason=None / run_meta.failure_category=no_patch |
| shop_api-134 | G1 (r0) | r0: runtime_dependency | record.failure_reason=None / run_meta.failure_category=no_patch |
| shop_api-134 | L0 (r0) | r0: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |
| shop_api-134 | L1 (r0) | r0: insufficient_evidence (abstained) | record.failure_reason=insufficient_evidence / run_meta.failure_category=abstained:insufficient_evidence |

For malformed runs the record's `insufficient_evidence` abstention is synthetic (`evidence_ids: []`); `diagnosis.json` is null and `run_meta.diagnosis_correct_class` is false.

Detail: shop_api-030 (lab_db exited) malformed in L0 r0, L0 r2, L1 r0, L1 r2, G0 r1, G1 r1 (L1/G1 inherit L0/G0 diagnosis); other 030 runs diagnosed `runtime_dependency` (e.g. G0 r0 rationale "The lab_db postgres container exited gracefully (exit 0, fast shutdown at 12:15:51...") and produced no patch (`failure_category=no_patch`). shop_api-134 L0/L1: `diagnosis.json` cause_class=insufficient_evidence, sufficient_evidence=false, rationale "The symptom is a fully passing test run. The runtime errors (DNS 'lab_db', POST /orders 500, /health timeout) are consistent with post-run teardown..."; G0/G1 diagnosed runtime_dependency. shop_api-026 behaves as expected in all conditions (runtime_dependency, no patch); 102/028/060: insufficient_evidence abstention with rationale "No evidence item ties any code location or configuration value to a failure".

## 5. Genuine repair failures (per-case detail)

### shop_api-020 (configuration, stage 2, r0): L0, G0 fail; L1, G1 verified
- Gold: `lab/shop_api/app/settings.py::Settings.redis_host` line 20; `gold_config_keys=["shop_api.REDIS_HOST"]`.
- Diagnosis (`diagnosis.json`): `cause_class=configuration`, `config_key=shop_api.REDIS_HOST`, `sufficient_evidence=true`; matches gold. L0 rationale: "shop_api's Settings defaults redis_host to 'redis-cache' (EV-0027), but the compose redis service is named lab_redis..."
- Patch (`repair.json attempts[1..3].edit_summary`, identical): `in lab/shop_api/app/settings.py: -    redis_host: str = "redis-cache" / +    redis_host: str = "lab_redis"`. Same file and line as gold, wrong value. `patch.diff` stores it (hunk @@ -17,7 +17,7 @@).
- Status: applied, tests failed. Each attempt: `visible_passed:false`, `counts: repro_passed 0, repro_failed 1, visible_passed 35, visible_failed 0`; `reproducer_outcomes: test_enqueue.py::test_confirmation_job_reaches_the_broker: failed`; `reasons: []`; `hidden_counts: {passed:0, failed:3}`; `repair.outcome=REJECTED`, `repair.reason=visible_failed`; `record.failure_reason=visible_failed`.
- Why still failing: L1 attempt-2 `feedback_received` (stored in `repair.json`) quotes the failure after the `lab_redis` edit: `socket.gaierror: [Errno -3] Temporary failure in name resolution` at `app/queue.py:39 enqueue_confirmation`. The edit copied the compose service name, which does not resolve in the reproducer sandbox.
- F1: attempt 2 edit `redis_host: str = "localhost"` -> reproducer passed; final `TEST_VERIFIED_IN_LAB`, `hidden_counts {passed:3, failed:0}` (L1 and G1).
- Root cause: **patch generation** (diagnosis, retrieval, policy fine; retrieval for L and G both contain `cfg:lab_db.REDIS_HOST`, G also `Settings.redis_host`). In F0 attempts 2 and 3 repeat attempt 1 verbatim (`feedback_received: null`).

### shop_api-019 (configuration, stage 2, r0): L0, L1 fail; G0, G1 verified
- Gold: `lab/shop_api/app/settings.py::Settings.coupons_valid_until` line 29; key `shop_api.COUPONS_VALID_UNTIL`.
- L0: `diagnosis.json` is `null`; `repair.json` has `attempts: []`; `record.failure_reason=invalid_output`; `run_meta.failure_category=abstained:invalid_output`, `diagnosis_rejected_calls: 2`, `diagnosis_correct_class: false`. `trace.json`: two `submit_diagnosis` calls, both `rejected:true`: `invalid arguments for submit_diagnosis: [{'type': 'string_too_long', 'loc': ('rationale',), 'msg': 'String should have at most 500 characters', ...`. The rejected input already names `coupons_valid_until='2026-01-01' (settings.py:29, EV-0028)`, so the right target was identified but the output broke the schema.
- L1: diagnosis inherited from L0; `requests.jsonl` empty; feedback never reached.
- G0: one rejected `submit_diagnosis` (same error) then accepted; patch verified. G1 same, verified.
- Root cause: **provider/model output** (500-char rationale cap violated).

## 6. L vs G and feedback

| Case | L0 | G0 | L1 | G1 | Note |
|---|---|---|---|---|---|
| shop_api-020 | fail | fail | ok | ok | feedback fixed it; L=G |
| shop_api-019 | fail | ok | fail | ok | difference from diagnosis output error, not evidence |
| shop_api-134 (non-repairable) | abstain, wrong class | runtime_dependency | same as L0 | same as G0 | G class-correct |
| shop_api-030 (non-repairable) | r0,r2 malformed | r1 malformed | same as L0 | same as G0 | |

L0 failed but L1 succeeded: shop_api-020 only. G0 failed but G1 succeeded: shop_api-020 only. No case has F0 success and F1 failure.

## 7. Genuine failures, compact rows

| case | cond | rep | diag class / target | gold match | attempts | edit | patch status | reason |
|---|---|---|---|---|---|---|---|---|
| shop_api-019 | L0 | r0 | insufficient_evidence / none | no (no diagnosis submitted) | 0 | none | NO_PATCH: diagnosis never submitted (invalid/malformed model output) | record.failure_reason=invalid_output |
| shop_api-020 | L0 | r0 | configuration / shop_api.REDIS_HOST | yes (config key shop_api.REDIS | 3 | att1: in lab/shop_api/app/settings.py: -    redis_host: str  | applied but visible reproducer failed (REJECTED) | record.failure_reason=visible_failed |
| shop_api-020 | G0 | r0 | configuration / shop_api.REDIS_HOST | yes (config key shop_api.REDIS | 3 | att1: in lab/shop_api/app/settings.py: -    redis_host: str  | applied but visible reproducer failed (REJECTED) | record.failure_reason=visible_failed |
| shop_api-019 | L1 | r0 | insufficient_evidence / none | no (no diagnosis submitted) | 0 | none | NO_PATCH: diagnosis never submitted (invalid/malformed model output) | record.failure_reason=invalid_output |

All 44 rows with full fields (rationale, gold target, edit summaries, visible/hidden counts, reason strings, stage and evidence) are in `results/analysis/failure_cases.csv`.

## 8. What we could not determine

- Why the model's rationale exceeded 500 characters: `requests.jsonl` stores hashes and token counts, not completions, and `trace.json` keeps only a truncated rejected input. Whether a length instruction or a higher rejected-call cap would have succeeded is untested.
- Whether the 030 malformed runs would have diagnosed runtime_dependency correctly (no diagnosis stored).
- Why the model chose `lab_redis` over `localhost` in 020 L0/G0 beyond the stored rationale (no reasoning trace). That F0 repeats the identical edit is evidenced by `feedback_received: null`; the pipeline code was not read.
- Whether retrieval differences (L vs G) affected any outcome: no failure traces to retrieval; L/G gaps (019, 134, 030) arise from model output differences, runs are single-sample with no cache, so noise cannot be separated (`report-all35-r0/tables/noise_pooled.csv` not analysed).
- Hidden failing test names for 019/020: only `hidden_counts` is stored.
- Stage-2 cases have r0 only, so 019/020 failure rates are single observations.
