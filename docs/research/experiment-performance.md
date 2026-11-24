# Experiment pipeline performance (23 Nov 2026)

Labels: **measured** = timed on this machine in this session or taken from recorded runs; **projected** = arithmetic from measured values. No AxForge tokens were used for any of this; model timings come from the 14 live AxForge calls recorded earlier in `runs/axforge_calls.jsonl`.

## 1. Where the time goes (before any change)
Per case, sequential, condition L0 or G0, AxForge `glm-5.3-flash` at reasoning effort high:
| Stage | Time | Status |
|---|---|---|
| Provider rate-limit waiting (AxForge) | 0 s: no limit hit in 15 requests; AxForge documents 8 concurrent calls and no RPM figure (BeatAPI free would add 65 s per request) | measured / documented |
| Model inference | 9-314 s per call, mean 80.5 s over 14 calls, 3-8 calls per case; about 85-95% of a case | measured |
| Prepare (copy lab, apply mutation, git init, evidence load, graph + BM25 index) | 0.4 s + 0.3 s | measured |
| Worktree create/apply/remove | 0.3 s each | measured |
| Sandbox container, per suite (Docker run incl. start and teardown) | reproducer 3.7 s, visible 3.8 s, hidden 3.1 s | measured |
| Sandbox per case | baseline reproducer + (reproducer + visible) per attempt + hidden once: about 15 s for 1 attempt, about 29 s for 3 attempts, 0 for abstentions | measured parts, projected sum |
| Patch generation | part of model inference | |
| Database writes | none (the experiment path runs without the incident DB) | by design |
| Result recording | atomic JSON files; not separately timed, negligible | not measured |
Model latency fits **latency = 26.5 s + 62 ms x output tokens** (n = 14, r = 0.88): reasoning/output tokens drive it, input size barely does. Whole-case wall times recorded earlier: 110 s, 179 s, 562 s (and 224 s for a run that hit a since-fixed bug); mean about 4 minutes.

**Why the 8-case L0+G0 pilot was estimated at 65 minutes:** 16 case-runs x about 4 minutes. Of that, about 58 minutes is model time and about 4 minutes is sandbox time (projected). Evidence for the 8 cases is a separate step: 8 x 28 s = about 4 minutes (a live-outage case takes 79 s).

**Why evidence for all 184 cases was estimated at 85 minutes:** 184 x 28 s = 86 minutes. Counting the 13 live-outage cases at 79 s it is about 97 minutes. Measured per-case split (shop_api-005): compose up + build 18.8 s, compose down 3.0 s, other compose calls 1.5 s, tree materialisation 0.07 s, trigger + collection about 1.5 s: 83% Docker start-up.

## 2. Classification
- Provider-bound (latency, no rate limit on AxForge): model calls. Sequential only because the runner was sequential; cases are independent.
- Docker-bound, independent per case: evidence collection (own compose project, ports, image tags), sandbox runs (unique container names).
- Truly sequential within a case: diagnosis -> patch -> visible test feedback -> next attempt -> hidden test.
- Shared one-off: sandbox image build (now done once before workers start).

## 3. What was implemented
| Change | Why it is safe |
|---|---|
| `runner --workers N` (cap 4 for AxForge; BeatAPI forced to 1) | each task has its own repo directory, containers and record file; records are atomic files; an outage stops new cases, in-flight cases finish, no record is written for the failed one, rerun resumes |
| AxForge in-flight token reservation | the 2.4M ceiling now counts requests in flight, not only completed ones |
| `lab_collect --jobs N` | per-case compose projects; bundles and keys written atomically |
| Evidence cache key per case (case files, lab hash, collector code) | a bundle is reused only if it was collected from exactly these inputs; unkeyed or stale bundles are recollected |
| Sandbox image ensured once before parallel runs | no concurrent build race |
| Per-case timings in `run_meta.json` (prepare, model, sandbox, other) | every future run reports where its time went |
| Worker cases use the worker sandbox configuration | found while checking concurrency: worker cases were being run with the shop_api sandbox workdir |
Unchanged: dataset and hashes, the four conditions, replicates, temperature and model settings, prompts (identical across conditions), patch policy, hidden-test execution, all recorded fields.

## 4. Measured before and after (no tokens)
| Measurement | Before | After |
|---|---|---|
| Evidence for 6 cases (005, 006, 007 outage, 008, 009, 021) | 215 s (jobs 1) | 90 s (jobs 3), 94 s (jobs 6): no gain beyond 3, the longest case (79 s) bounds it |
| Evidence bundles, parallel vs sequential | n/a | identical kinds and identical deterministic content (config, compose, trace frames) for 6 of 6; logs and health differ only by time |
| 3 sandbox pipelines at once | about 12-15 s each alone | 19 s for all three; per-suite times 3.3-4.3 s (no slowdown), identical results |
| Leftover containers after parallel runs | n/a | 0 |
| Tests | 619 passed | 631 passed, 23 skipped; ruff and format clean |

## 5. Projections (not measured: AxForge was not called)
| | Before | After |
|---|---|---|
| Evidence for the 8 pilot cases | about 4.5 min | about 2 min (jobs 3) |
| Evidence for all 184 cases | about 97 min | about 40 min (jobs 3-4; from the measured 2.4x) |
| Pilot model + sandbox, 16 runs | about 62 min sequential | about 15-20 min with 4 workers (total model time about 58 min / 4, bounded by the longest single case of about 9-10 min) |
| Pilot total including evidence | about 65-70 min | about 20-25 min |
| Provider requests and tokens | unchanged: about 300k tokens, 16 case-runs x 3-8 calls | unchanged |
Uncertainty: AxForge may slow individual calls under 4 concurrent requests; a 429 or `too_busy` response stops the run (no retry, no record) and the rerun resumes.

## 6. Needs approval (could affect validity)
1. **Reasoning effort** `high` -> lower: model time scales with output tokens, so this is the biggest lever, but it changes the model setting for all conditions and may change quality. Not applied.
2. **Cache sandbox results by (case, patch hash, suite, image, dataset hash)**: saves about 4-5% when two conditions propose the identical patch. Safe if keyed as stated and if timeouts are never cached. Not implemented.
3. **Shorter prompts**: little time effect (input size barely moves latency); would change prompts. Not applied.

## 7. Measured on the real L0/G0 pilot (23 Nov 2026; AxForge `glm-5.3-flash`)
Section 5 projected the pilot at 20-25 minutes with 4 workers. That did not hold:
| Item | Projected | Measured |
|---|---|---|
| Workers | 4 | **1**: with 4 concurrent requests AxForge returned 429; it also returned 429 for sequential requests (at most 1 request in the previous minute), so the cap was set to 1 with a 10 s minimum gap |
| Provider stops | none expected | several (429 and one connection hang of about 10 minutes); each stopped the run with no retry; the run id was resumed after a pause (300 s in the supervised loop) |
| Tokens, 16 case-runs plus shop_api-004 and earlier probes | about 300k for the pilot | 310,010 committed in the whole ledger, of which 18,078 are estimates for failed requests |
| Wall time | 20-25 min | far longer, spread over several interrupted passes; the supervised pass logged L0 resume at 16:20, a 300 s pause after the stop, one more L0 case finishing about 17:25, then G0 to completion. Exact per-case timings are in each `run_meta.json` (not summarised here) |
Consequence: parallelism is not a lever on this provider; the dominant cost is model latency plus provider instability. The "4 workers" option in section 3 and the cap-of-4 statement remain in the code only as an upper bound that AxForge runs never use. No methodology setting (reasoning effort, prompts, temperature) was changed to speed anything up.


## 8. Cache and attempt behaviour measured on the fix (24 Nov 2026)
- **Cost of a live attempt after the fix:** F0 attempts 2 and 3 are now real requests. Patch replies were 71-154 visible output tokens each (a one-block SEARCH/REPLACE). Per case, L0 on the four new cases recorded 13.1k-21.7k input and 0.6k-1.0k output tokens (diagnosis plus 3 patch calls). The replies at attempts 0, 1, 2 were identical in 8 of 8 prompt groups, so extra F0 attempts bought nothing at temperature 0.
- **Run time (one worker, 10 s spacing, no provider stop):** the 3-case test group took about 5 min (L0), 0.5 min (L1, all cache), 6.5 min (G0), 1.5 min (G1, all cache); dev 001 took about 1.5 min for L0 and for G0.
- **Cross-condition cache reuse** (identical request, temperature 0) made L1 and G1 cost 0 tokens here; that is why those runs are not independent samples.
- **Tokens this pass:** AxForge 149,130 (committed total 459,140, remaining 1,940,860). BeatAPI development ledger: 23 requests, 106,126 in and 32,892 out; its resumed run finished 002 and 003 without a provider failure.


## 9. Cost and time after the verbatim-source fix (24 Nov 2026)
- **Prompt size:** the patch prompt's target section went from a truncated evidence rendering to the whole target file (about 3,000 characters for the `settings.py` cases; larger files are windowed at 8,000 characters). Patch requests measured 2,957 input tokens (attempt 1) and 3,456 (with 2,000 characters of feedback) on dev 001, against output of 63-226 tokens.
- **Token cost of the 4-case x 4-condition experiment:** about 130k tokens for AxForge in total, because the diagnose stage was served from the cache (its prompts did not change) and only patch requests were new; L1/G1 attempt 1 were cache hits. Validation run on dev 001 about 10.3k. Ledger: 601,223 committed, 1,798,777 remaining.
- **Time (one worker, 10 s spacing):** test group L0 about 4 min after an initial 429 stop and a 300 s pause, L1 about 3.5 min, G0 about 4 min, G1 and dev L0 together under 6 min; dev L1, G0 and G1 about 1-2 min each. One provider stop (HTTP 429 at the start of the L0 test run); the supervisor resumed the same run id.
- **What the fix changes in cost:** more cases now reach the sandbox (about 4 s per suite) instead of ending at `no_match`, so per-case wall time rises by the visible-suite runs (about 8-15 s per attempt) and tokens rise slightly for feedback prompts; model latency still dominates.


## 10. Screening phase cost and time (24 Nov 2026, patch_v4)
- **Tokens:** list A (8 cases, L0) 218,186; list B (3 cases, L0) 18,524, cheaper because the diagnose responses of the earlier pilot were legitimately reused (identical prompts). Mean for a case that abstained: about 30k tokens (6 tool calls of about 5k input each, then abstention); a case reaching the patch stage with the new prompt adds about 3k input and 0.1-0.5k visible output per attempt, but hidden reasoning tokens can reach the output cap.
- **Time:** about 10 min per case for list A (the model's reasoning dominates; plus AxForge 429 stops: rounds 1-2 failed immediately and were paused 300 s each; rounds 4-6 were the truncated-reply stall of case 018 described in readiness 13.3, which wasted 15 min of pauses). Total wall time for list A about 1 h 40 min; list B about 8 min; the L1/G0/G1 runs on 010 about 15 s each (cache, or crash before any request).
- **Waste to avoid next time:** a deterministic failure (cached truncated reply) was being retried as if it were a transient provider outage; it is now a recorded result. The supervisor's "no progress" guard stopped it after three resumes.
- Ledger: 837,933 committed, 1,562,067 remaining.


## 11. dev-d1 smoke stage cost (24 Nov 2026)
3 cases, L0, diagnose-only, live requests: 50,966 tokens (7,605 / 18,006 / 25,355 per case); 6 requests; model-reported latency 160 s / 594 s / 225 s per case (the 058 case waited on the provider). Prompt about 20k characters (about 5k tokens) per request; 1 to 3 requests per case. Ledger 923,207 committed, 1,476,793 remaining. Estimated remaining cost of the six-case L0+G0 diagnosis stage: about 12 case-runs x 25k = about 300k (worst case about 12 x 50k).


## 12. dev-d1 Level-1 evaluation cost (24 Nov 2026)
23 live requests, 176,589 tokens in this invocation = 155,796 (six-case L0 89,680 plus G0 66,116) + 35,769 (controls: L0 14,308, G0 21,461) - 14,976 (the preserved 014 L0, paid for earlier). Per request about 6.2k to 8k input and 0.03k to 2.5k output. Wall time of the whole invocation about 12 minutes (30 s shared pacing between request starts; model time 474 s L0, 226 s G0 on the six cases). Ledger 1,114,772 committed, 1,285,228 remaining.


## 13. dev-d1 patch stage cost (24 Nov 2026)
12 requests, 48,800 tokens in total (L0 24,419, G0 24,381): about 4.1k tokens in and 16 to 22 tokens out on average per request, far below the audited estimate (about 63k expected, 479,973 worst case). Estimated input (3 chars per token) was 4.7k to 5.5k per prompt; reported input was 3.7k to 4.4k. Model time 5.6 to 13.7 s per request; sandbox about 15 s per case (baseline visible run plus reproducer, visible and hidden suites); wall time of the invocation about 6 minutes for both runs (30 s shared pacing). Ledger 1,163,572 committed, 1,236,428 remaining.
