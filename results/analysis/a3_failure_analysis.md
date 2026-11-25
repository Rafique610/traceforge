# A3 failure analysis (P4-S02)

Status: draft by Rafique, 25 Nov 2026, **NEEDS REVIEW**. Ruhan normally owns the agent/repair rows (A1 to A4); he is on a break this week, so Rafique drafted them from the stored records and they are marked for his review.

No model, network or retrieval call was made to write this. Every row comes from a stored artifact named in its row.

## Sources

| Id | What | Where |
|---|---|---|
| S1 | RC1 final evaluation, paid model (AxForge), conditions L0/G0/L1/G1, 35 sites, 220 case-runs, 44 not verified | `results/analysis/failure_cases.csv` (44 rows), `docs/research/failure-analysis.md`, `results/analysis/rc1-paired-stats/rc1_stats.md` |
| S2 | Live runs on the free model (BeatAPI `glm-5.3-flash-free`) through the real Investigate path, 25 Nov 2026: 10 investigations (8 command-line runs + 2 from the browser) | `runs/validation/beatapi-e2e-*.log`, usage ledger `runs/beatapi_usage.jsonl` (30 calls) (both git-ignored, local) |
| S3 | P5-S06 retrieval benchmark on three code bases (itsdangerous, requests, the lab), 45 queries, arms RET-L (keyword) and RET-G (keyword + code map) | run `review-repos`, `results/retrieval/review-repos/per_query.csv` (git-ignored; rerun with `task bench:retrieval SUITE=repos RUN_ID=review-repos`); summary in `docs/research/retrieval-benchmark-baselines.md` |

**Caution on S3.** The retrieval gold answers are AI-drafted and not yet human-checked: all 98 rows of `benchmarks/retrieval/second_review.csv` have an empty reviewer column. A "miss" in R1 to R5 is a miss against an unchecked label.

**Caution on S2.** One or two tries per bug, on our own planted bugs. These rows show *kinds* of failure, not rates.

## 1. Grouped table

Categories use the P3-S02 taxonomy. One category is new and marked as such, because the taxonomy has nothing for "the model's answer broke the required format".

| # | Category | Count | Example case ids | What went wrong (plain words) | Planned fix | Maps to | Owner |
|---|---|---|---|---|---|---|---|
| A1 | **MODEL_OUTPUT_INVALID** *(new)* | 8 case-runs (S1): 2 on a fixable bug, 6 on a non-fixable one | shop_api-019 L0/L1; shop_api-030 (6 runs) | The diagnosis explanation was over the 500-character limit, so the tool rejected it twice and the run gave up. On 019 the rejected text already named the right setting (`coupons_valid_until`). A correct answer was lost to a format rule. | Accept and log an over-long explanation instead of rejecting it, or state the limit in the prompt. Implemented as the RC2 candidate; not yet validated on unseen bugs. | P5-S10 | Ruhan |
| A2 | TEST_ENVIRONMENT_FAILURE | 2 case-runs (S1) | shop_api-020 L0, G0 | Right file, right line, right setting (`REDIS_HOST`), wrong value. The model used the compose service name `lab_redis`, which works in the real stack but does not resolve inside the test sandbox. Without feedback it repeated the same edit three times. With feedback (L1/G1) it switched to `localhost` and passed. | Refuse an identical second patch and ask for a different value (repeat guard, RC2); suggest candidate values from the config flow. | P5-S10, P5-S13 | Ruhan |
| A3 | SIMILAR_SYMPTOM_WRONG_CAUSE | 2 case-runs (S1), no effect on outcome | shop_api-134 L0, L1 | A dependency outage (database DNS failing) was read as "not enough evidence": the model judged the errors to be teardown noise after a passing test run. The code-map arm (G0/G1) got it right. No patch either way, so the outcome is the same. | Feed runtime evidence (container state, error timing) to the diagnosis so a live outage is not dismissed as noise. | P5-S14 | Ruhan |
| A4 | COST_OR_TIMEOUT (output budget) | 3 investigations ended inconclusive; 10 of 30 calls hit the cap (S2) | shop_api-017 (2, one from the browser), shop_api-003 (1) | The free model spends most of its answer on hidden reasoning. At 2,048 tokens and again at 4,096, some diagnosis answers were cut off before the tool call, so the run ended "inconclusive". The same bug (017) was fixed on another try: this is variance, not a wrong idea. | Done: the cap was raised to 4,096 (7eb6487). Open: measure the rate with repeat runs (3 per bug), then compare models on output length. | P5-S04 (model sensitivity) | Rafique |
| A5 | TEST_ENVIRONMENT_FAILURE (provider down) | 1 investigation (S2) | shop_api-011 first try | The free provider could not be reached, so no AI call was made. Rerun later: fixed and verified. Not an AI failure, but a live demo would show it. | Retry once after a pause; for the demo, a recorded backup run. | Deferred (demo prep, not a research step) | Rafique |
| R1 | LOW_RETRIEVAL_RECALL (symptom with no code words) | 5 queries | it07, it08, rq06, rq07, lb07 | The report describes only what the user sees ("old emailed links stopped working", "accented letters come out garbled"). Keyword search needs shared words, and the code map needs a starting point; neither exists. 5 of the 6 queries of this type were missed in the top 10 by both arms. | Give search the clues a real incident has: stack-trace frames and log lines as anchors (runtime evidence). Rewriting the symptom into likely code words is deferred. | P5-S14 | Rafique |
| R2 | LOW_RETRIEVAL_RECALL (paraphrased bug) | 2 queries | it06, rq05 | The report uses different words from the code ("shrink" vs `compress`, "no length header" vs `prepare_content_length`). | Same as R1. Embeddings were tested and rejected (P5-S08 NO-GO), so the next try is expanding query words from the evidence. | P5-S14; deferred | Rafique |
| R3 | LOW_RETRIEVAL_RECALL (answer spread over files) | 2 queries | it15, rq15 | The answer spans several functions in different files (encode and decode of a timestamp; cookies on redirects). A top-10 list fills up with one side and misses the other. | Return results grouped by file and call chain instead of a flat top 10. | P5-S12 | Rafique |
| R4 | MISSED_DEPENDENCY | 1 query | rq09 | The error comes from a JSON call made inside `prepare_body`; the query names the error, not the function, and the call edge to the JSON helper is not followed back to its caller. | Walk call edges in both directions (caller of the failing call). | P5-S12 | Rafique |
| R5 | MISBOUND_CONFIG_KEY | 2 queries | lb10, lb13 | The setting lives in compose (`REDIS_HOST` in the shared app environment) or in worker settings (`MAX_RETRIES`, `BACKOFF_BASE_S`); the report says "broker address" and "retried too many times". Nothing links those words to the keys. | Config value-flow: link each key to where it is read and to what it controls. | P5-S13 | Rafique |

**Totals:** 10 groups; 28 analysed failures (12 case-runs in S1, 4 investigations in S2, 12 queries in S3); 6 taxonomy categories + 1 new. Rafique's area: R1 to R5 plus A4, A5 (7 groups). Agent/repair area: A1 to A3 (3 groups, Ruhan to review).

Not included: the 32 RC1 case-runs where the model correctly refused a non-fixable bug (expected behaviour; listed in `docs/research/failure-analysis.md` section 4), and the free-model runs that ended correctly (002, 011, 017, 003, 004 on their good tries).

## 2. What each baseline difference means

| Comparison | Numbers | Reading |
|---|---|---|
| Keyword (L0) vs keyword + code map (G0), repair | fixed 27/35 vs 28/35; 1 discordant site; exact p = 1.000 (S1, `rc1_stats.md`) | **No difference.** The one site that differs (019) failed on the format rule in A1, not on retrieval. |
| L0 vs G0, diagnosis class | 32/35 vs 35/35; 3 discordant; p = 0.250 (S1) | G0 is never worse here, but 3 sites cannot support a claim. The 3 are 019 and 030 (row A1, format rule) and 134 (row A3), all model-output effects. |
| No feedback (L0/G0) vs feedback (L1/G1) | 27 to 28 and 28 to 29 of 35; 1 discordant each (S1) | Feedback fixed exactly one site (020, row A2). Not significant; a real but single example of the repair loop working. |
| RET-L vs RET-G, retrieval on 3 code bases | recall@10 0.556 both; MRR 0.393 vs 0.397; 45 queries (S3) | **No difference** on these queries. The code map does not help when the query has no code words to start from (R1, R2): the misses are a query problem, not a ranking problem. |
| Paid model vs free model | paid: 27 to 29 of 29 fixable fixed, 6/6 refused (S1); free: right answer on every bug tried at least once, but 4 of 10 live investigations ended without a result: 3 cut off, 1 provider outage (S2) | Same pipeline, same checks; the free model is less reliable mainly because it runs out of answer space (A4), not because it diagnoses wrongly. Rates need the planned repeat runs. |

## 3. Product defects found during live testing (not model failures)

| Defect | Status |
|---|---|
| The website could not start a lab bug; a typed-in incident failed with a bare "error 422" | Fixed, ff5ca6b |
| Report summary said "No symptom recorded" for every lab bug | Fixed, 842b760 |
| Symptom evidence is labelled service `lab_db` instead of the failing service | Open: the label is set in `agent/symptom.py`, an RC1-locked file; changing it changes the RC1 fingerprint. Deferred until after the RC1 results are final (P6-S03). |

## 4. What this analysis cannot tell

- Rates. S1 has one replicate on 23 of 35 sites; S2 has one or two tries per bug. A4 and A5 need the planned 3-tries-per-bug run.
- Whether the R-rows are real misses: the retrieval labels are unchecked (see the caution above).
- Generalisation: every bug here is planted in our own practice app; no unplanted bug has been tried yet.
