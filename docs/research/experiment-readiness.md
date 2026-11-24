# Experiment readiness (23 Nov 2026)

Status (see sections 11-13 for corrections to sections 7, 9, 10): **dataset ready with limitations; experiment infrastructure wired for the frozen split; official AxForge pilot L0/G0 completed (section 7); L1/G1 completed (section 9, cache replays, feedback not exercised).** Everything below is measured or checked in the repository on 23 Nov 2026. Sections 1-6 are pre-pilot; section 3 and 6 figures are superseded by sections 7-8. Pilot outcomes are an 8-case sample, not a research conclusion.

## 1. Frozen dataset audit (deterministic, no model calls)
- 184 validated cases: test 151 (60 configuration, 67 application_code, 12 runtime_dependency, 12 insufficient_evidence), dev 33 (16/15/1/1). Test: 35 variant groups, 20 families, 115 shop_api + 36 worker, 127 at distance >= 1.
- Freeze intact: the manifest hash, the content hash over every test case's files and the lab base SHA all match `freeze.json` (`881f2887...`, `6c004192...`, `5ec94a43...`). Nothing changed after `cd1acaa`.
- Every case: manifest valid, case files, reproducer, hidden tests (all 158 repairable cases: 127 test + 31 dev), gold labels and a passing 3x validation record; hidden suites are red on the fault and green on the original and the gold fix. No leakage (hidden-only test names never appear in model-visible text; shared names between reproducer and hidden suite are by design).
- Limits: author bias (one author, no blind peer check of a sample); manual graph distances; dev case `shop_api-001` shares variant group `settings_default:shop_api:redis_host` with test cases 020, 040, 139 (do not tune on it); configuration and code cases have no traceback frames in their evidence (only outage cases do: shop_api-007 has 12), so the graph condition relies on configuration binding and symptom terms for most cases.

## 2. Problems found and fixed in the experiment path (all regression-tested)
| Problem | Fix |
|---|---|
| `eval:run` used sample cases only | `--real` path (`evaluation/real_run.py`): committed case -> faulty repo -> saved evidence -> real retrieval -> sandboxed repair loop -> record |
| Evidence collection regenerated the dataset per case (timed out at 340 s) | builds the tree from `datasets/cases/<id>/mutation.patch`; about 28 s per case (79 s for a live outage); resume-safe batch |
| Hard-coded symptoms for 4 cases | `agent/symptoms.py`: deterministic per case, passes the leakage scan for all 184 |
| Conditions pinned `devstral`/`mistral` | default `axforge` / `glm-5.3-flash`; provider and model are a run-level override; `tier` = official only for axforge glm-5.3-flash |
| Bare config key vs gold `service.KEY` | tool description asks for `service.KEY`; a bare key is qualified with the case's own service (a wrong service stays wrong) |
| Patch prompt did not say which files are editable | patch prompt v3 (equal for all conditions); before: 3/3 attempts on dev case 001 edited `lab/compose.yaml` and were rejected |
| **Gold fixes rejected by the literal rule** | the policy rejected the repo's own gold fix for 29 of 76 configuration cases and 1 code case, because a settings default equal to a literal in the tests counted as special-casing. Class-level field defaults are now exempt (module-level constants are still checked). After the change 157 of 158 repairable gold fixes pass; `shop_api-035` is still rejected and is reported as unrepairable by policy |
| A provider outage was recorded as a crash result | `StopRun` is now one class for the runner and `real_run`; an outage keeps the artifacts under `<case>.r0.provider_error.<ts>/`, writes no record, and a rerun resumes |
| Relative dataset path broke the sandbox | paths are made absolute |
| BeatAPI pacing counted from send, not completion (caused the 429) | pacing counts from the later of send and completion; completion is stamped even on errors |

## 3. Providers and budget
- **BeatAPI `glm-5.3-flash-free` (development only).** Read-only usage endpoint: balance 0, credits settled 0, only the free model, no violations. The free limit is 1 successful request per minute per account; a 503 `upstream_timeout` occurs occasionally and is never retried automatically. Development runs live in `results/development/`, ledger `runs/beatapi_usage.jsonl` (13 requests, 68,238 in / 19,894 out). Not official.
- **AxForge `glm-5.3-flash` (official).** Ledger `runs/axforge_usage.jsonl`: 15 requests, 54,703 in / 12,274 out = 66,977 tokens; internal ceiling 2,400,000; remaining to ceiling 2,333,023. This figure is provider-reported usage recorded by the gateway; it has **not** been compared with the AxForge dashboard, and the API gives no free-versus-paid field, so "free" is unconfirmed. No official run has been made. A card is on file; the dashboard check (balance, auto top-up off) is the owner's.
- Results: `results/official/` and `results/development/` are separate; development is never included in official tables.

## 4. Development results (BeatAPI free, condition L0, 4 dev cases, 1 replicate; DEVELOPMENT ONLY)
| Case | Outcome | Notes |
|---|---|---|
| shop_api-001 | REJECTED (visible tests fail) | diagnosis exact (`shop_api.REDIS_HOST`); patch accepted by policy, wrong value (`lab_redis`, gold `localhost`) |
| shop_api-002 | TEST_VERIFIED_IN_LAB | hidden 3/3 pass, first attempt |
| shop_api-003 | NO_PATCH | runtime dependency, correct |
| shop_api-004 | not completed | BeatAPI returned 503 `upstream_timeout` on two separate attempts (not retried automatically); the run stopped cleanly and no result was recorded for this case |
Per-case tokens measured on the free provider: 6.8k-35.6k in, 2.1k-6.2k out. These runs exercised the infrastructure; they are not evidence about model quality.

## 5. Optimisation: investigated and measured
- **Implemented:** response cache reuse (reruns of identical prompts cost 0 new tokens: three pilot reruns); one gateway attempt, no automatic retry; completion-aware pacing; separate ledgers; the patch prompt v3 (does not change tokens: 19.0k vs 19.2k in on case 001, but removes a 100% systematic rejection); policy exemption above (removes a systematic false negative).
- **Rejected or not done:** batching and concurrency (the free provider allows one request a minute; official runs stay sequential so the ledger stays exact); dynamic context trimming and prompt-prefix caching (no evidence yet that context size drives errors; would change the experiment; revisit after the pilot).
- No quality regression was measured because no baseline comparison on the frozen set exists yet.

## 6. Pilot estimate for AxForge (not started; needs approval)
Basis: measured per case on AxForge earlier (4 dev cases): mean 15.3k input + 3.2k output = about 18.5k tokens and about 4 minutes per case at reasoning effort high.
| Option | Runs | Tokens | Share of 2.4M | Time |
|---|---|---|---|---|
| A: 8 test cases (3 config, 3 code, 1 runtime, 1 insufficient) x L0, G0, 1 replicate | 16 | about 300k | 12% | about 65 min + 4 min evidence |
| B: 12 test cases x L0, G0 | 24 | about 445k | 19% | about 100 min |
| Rubric scale: 50 cases x L0, G0 | 100 | about 1.85M | 77% | about 7 h |
| Full design: 50 cases x 4 conditions x 1 replicate | 200 | about 3.7M | over the ceiling | not possible |
Recommendation: Option A first. Retrieval (E1) and the rule baseline need no tokens and can run on all 151 cases once their evidence bundles are collected (about 28 s per case, about 85 minutes for all 184).
Risks: only outage cases have trace frames, so G may show no advantage on configuration and code cases; one case (shop_api-035) cannot pass the policy; reasoning-token variance is large (one case used 7.7k output tokens).

## 7. Official AxForge pilot, conditions L0 and G0 (completed 23 Nov 2026)
Provider `axforge`, model `glm-5.3-flash`, temperature 0, 1 replicate, 1 worker, frozen test split. Run ids `official-axforge-L0-pilot8` and `official-axforge-G0-pilot8` in `results/official/`. Cases: shop_api-005, 006, 007, 008, 009, 010, 012, 013 (8 per condition; 011 was skipped).

| Case | L0 | G0 |
|---|---|---|
| 005, 007, 008, 009, 012 | NO_PATCH | NO_PATCH |
| 006, 010 | REJECTED | REJECTED |
| 013 | TEST_VERIFIED_IN_LAB | TEST_VERIFIED_IN_LAB |

- Totals per condition: 5 NO_PATCH, 2 REJECTED, 1 TEST_VERIFIED_IN_LAB. Only shop_api-013 was repaired. L0 and G0 outcomes are identical case by case.
- **Reading:** no difference between L0 and G0 was observed in this sample (8 cases, 1 replicate, outcome labels only). This is too small to support any claim about the effect of graph retrieval, for or against; it is not an estimate of that effect.
- L1 and G1 on the same cases: see section 9.
- **Provider interruptions (AxForge).** The runs were stopped several times by provider-side failures; per the halt rule none was retried inside a request. Evidence: `<case>.r0.provider_error.<ts>/` folders in the official run directories (L0: shop_api-005, 006, 008; G0: folders from stopped attempts) and the ledger's error rows. Observed: intermittent HTTP 429 responses, including when only one request had been sent in the preceding minute (so a request-rate cause was ruled out), and one connection hang of about 10 minutes. A stopped case writes no record; the same run id was resumed after a pause. During the final supervised resume, L0 stopped once (5 to 7 records), was resumed after a 300 s pause, and finished (8 records); G0 then ran to 8 records without a stop. No record was edited or relabelled; every case has exactly one record per condition.
- Concurrency: 4 concurrent requests also produced 429s earlier, so the runner now forces 1 worker for AxForge and spaces requests by at least 10 s.
- Earlier AxForge attempt: dev case shop_api-004, L0 (`results/development/dev-axforge-L0-shop_api-004/`): NO_PATCH through the abstention path after the tool-call budget was exhausted. It is a development-split case; its metadata carries the official tier label because of the provider and model, but it is not counted in the test-split pilot.

## 8. AxForge budget after the L0/G0 pilot
Usage report (ledger `runs/axforge_usage.jsonl`, provider-reported plus estimates): **310,010 tokens committed**, which includes **18,078 estimated tokens for failed requests** that may have been processed (timeouts, 5xx), counted as used so the budget can only look smaller than reality. Remaining to the internal ceiling of 2,400,000: **2,089,990**. The 600,000 reserve (3,000,000 stated allowance minus the ceiling) is untouched. Every request is gated by an explicit billing-verified flag, a ledger check, an in-flight reservation and halt-on-first-failure. These figures are not reconciled with the AxForge dashboard. BeatAPI usage is in its own ledger and is not included.

## 9. Official AxForge pilot, conditions L1 and G1 (completed 23 Nov 2026)
Run ids `official-axforge-L1-pilot8` and `official-axforge-G1-pilot8` in `results/official/`, same 8 cases, provider, model, settings and 1 worker as section 7. Both runs completed 8 of 8 in about one minute each, with **0 new AxForge tokens and no provider stop**.
- Outcomes are identical to L0/G0 for every case: 5 NO_PATCH (005, 007, 008, 009, 012), 2 REJECTED (006, 010, failure_reason `no_match`), 1 TEST_VERIFIED_IN_LAB (013).
- **Why no tokens were used (verified in the code and records):** at temperature 0 every request was byte-identical to the L0/G0 request, so the gateway cache served all of them (`cache_hits` equal to the number of calls, token fields equal to L0/G0). The feedback factor changes a prompt only after an attempt has been applied and run on the visible tests (`repair/loop.py`: `last_visible` is set only then). In this sample no such case occurred: 006 and 010 failed all 3 attempts at the edit-matching step before any visible run, 013 passed on attempt 1, and the other five abstained. So F1 had nothing to feed back.
- **Reading:** this pilot contains no evidence about the effect of visible-test feedback; the sample did not exercise the factor. It says nothing for or against it. Cases where a patch applies but fails visible tests are needed. The records carry the L0/G0 token counts because their model responses were replayed from the cache; they are not new independent samples and must not be counted as extra replicates.
- AxForge budget unchanged: 310,010 committed, 2,089,990 remaining to the 2.4M ceiling.

## 10. Development runs after the pilot (23 Nov 2026; DEVELOPMENT ONLY)
- **BeatAPI dev G0, shop_api-001..003** (`results/development/dev-beatapi-G0-dev001-003/`, glm-5.3-flash-free): shop_api-001 recorded REJECTED (18,410 in / 3,459 out in the record; 2 of its calls were cache hits). The run then stopped on a provider error at shop_api-002 (artifacts in `cases/shop_api-002.r0.provider_error.1795442127/`, no record, no retry). shop_api-002 and shop_api-003 are **incomplete, not skipped**; resume the same run id when BeatAPI is available.
- **AxForge dev G0, shop_api-004** (`results/development/dev-axforge-G0-shop_api-004/`): NO_PATCH, `budget_exhausted`, 6 tool calls, 24,576 in / 5,767 out. This is the same outcome and the same token counts as L0 (`dev-axforge-L0-shop_api-004`): all requests were byte-identical to the L0 requests and were served from the gateway cache (5 cache hits; the AxForge ledger did not move: 310,010 committed, 2,089,990 remaining). No observed difference between L0 and G0 on this single case; the G0 record is a replay, not an independent sample. Dev case, not part of official tables.


## 11. Validity audit and cache/feedback fix (24 Nov 2026) - supersedes the readings in sections 7, 9 and 10
**Read this section first: it corrects how the earlier pilot results must be interpreted.** No result file was edited or deleted.

### 11.1 Design, as implemented (checked in `docs/plans/ARCHITECTURE.md`, `DECISIONS_AND_OPEN_QUESTIONS.md` D10/D26, `repair/loop.py`)
- L0 = lexical retrieval, F0; G0 = graph retrieval, F0; L1 = lexical, F1; G1 = graph, F1.
- **"Three attempts" means up to 3 repair attempts per case inside one run, in both F0 and F1.** F0: each attempt starts fresh (no feedback); F1: attempt n sees the visible-test output of attempt n-1. Hidden tests run once, on the final patch, and never feed back.
- **"Three replicates" is a separate thing:** the full 2x2 (A4) is specified x 3 independent replicates (replicate index in the cache key, D26). **Every result so far is replicate 0 only. The 8-case L0/G0 pilot does not meet the 3-replicate requirement and was never meant to.**

### 11.2 What was broken (root causes, verified)
1. **F0 attempts 2 and 3 were cache replays of attempt 1.** The cache key was prompt + model + replicate index. F0 sends the same prompt for every attempt, so attempts 2 and 3 were served from the cache: "3 attempts" was one attempt counted three times (cases 006 and 010 in L0: 3 attempts, `cache_hits` 3; dev 001 under BeatAPI the same). Fix: a new `attempt_index` field is added to the cache key **only for attempts after the first** (never sent to the provider, prompts unchanged). Attempt 1 keeps its original key, so existing cached responses stay valid and nothing else changes. Replicate independence (replicate index in the key) was already correct and is now covered by a test.
2. **Cross-condition reuse is legitimate and is kept:** when two conditions send a byte-identical request at temperature 0 the stored answer is reused. That is safe, but it means such runs are not independent samples.
3. **F1 never received feedback in any pilot run, and why.** Feedback is the visible-test output of the previous attempt, so it exists only after an attempt's edit applied and the visible suite ran (`last_visible` in `repair/loop.py`). In the pilot, no attempt reached the visible suite except the passing ones. The mechanism itself works (unit tests: attempt 2 and 3 prompts carry the visible output, attempt 1 does not, hidden text never appears).
4. **Why attempts do not reach the visible suite (new finding):** in every new run below, all 3 attempts failed with `no_match`: the model's SEARCH text does not match the file. The patch prompt shows configuration targets as rendered evidence lines (for example `settings.redis_host [str] = 'redis.local'`), not the verbatim file text, so the model quotes a line that does not exist in the file. This is a property of the patch prompt/context shared by all four conditions. It was not changed (see 11.6).
5. **At temperature 0 the provider returns the same visible reply for every attempt** even when the requests are now separate live calls (8 prompt groups checked: replies identical, hidden reasoning-token counts differ). So F0's 3 attempts are 3 real calls but effectively one distinct patch: F0 gets no diversity from retrying.
6. **Graph retrieval often equals lexical retrieval.** Measured without model calls (`render_context` of L vs G): the context sent to the model is **byte-identical for L and G on shop_api-002, 004, 005, 006, 008, 009, 010, 012, 013** and differs only on 001, 003, 007 (cases with trace frames). On the new cases 001, 020, 040, 139 the prompts differ between L and G (different message hashes). Consequently G0 on 005, 006, 008, 009, 010, 012, 013 and dev 004 were replays of L0 (same tokens, cache hits).

### 11.3 Audit of existing results (nothing relabelled)
| Result | Status |
|---|---|
| Official `L0-pilot8`, 8 cases | Real executions (replicate 0). Within the run, attempts 2-3 of 006 and 010 were replays of attempt 1 (bug 1); calls re-served after a provider stop were reuse of already-completed calls. Valid as "one attempt's worth" of evidence per case. |
| Official `G0-pilot8` | **007 only is an independent execution** (G context differs; 0 cache hits; different tokens). **005, 006, 008, 009, 010, 012, 013 are replays of L0** (identical context, identical tokens). |
| Official `L1-pilot8`, `G1-pilot8` | **All replays** of L0/G0 (tokens equal, cache hits equal to the calls made). Feedback was not exercised in any case (no attempt had a visible-test output to feed back). Not independent, not usable as L1/G1 evidence. |
| Dev `dev-axforge-L0-shop_api-004` | Real execution. `dev-axforge-G0-shop_api-004` is a replay (G context identical). |
| Dev BeatAPI `pilot1`-`pilot7` | Development iterations on 4 dev cases (prompt/policy changes between runs, repeated reruns of 001 served partly from cache); not comparable to each other or to official results. |
| Dev BeatAPI `G0-dev001-003` | Completed 24 Nov: **001 REJECTED** (3 attempts, visible suite ran 3 times, produced under the old cache key so attempts 2-3 were replays of attempt 1), **002 TEST_VERIFIED_IN_LAB**, **003 NO_PATCH**. Resumed with the run id, one process, no provider failure. 001 is the only result in the repository where an edit applied and failed the visible tests. |
| Incomplete runs | None remain among the above. Provider-error folders are kept as artifacts. |

**Valid for comparison today:** only the official L0 pilot (replicate 0) and the new runs in 11.5. **Not valid as independent evidence:** every G0 record except 007, every L1 and G1 pilot record, dev 004 G0.

**Leakage check (no model calls):** the 57 cached provider requests contain no hidden-suite test name (22 distinct names checked), no "hidden", "gold" or "mutation.patch" text; the runner's hidden-leak guard also checks every request (`hidden_guard_calls` in each case's `run_meta.json`). The gold fix is defined as the reverse of the mutation patch and is not in any prompt. Limit: the scan covers the cached requests present on disk.

### 11.4 Changes made (all regression-tested; no methodology, prompt, condition, temperature, policy or dataset change)
- `agent/gateway.py`: `attempt_index` (cache key only, only when > 0). `agent/patch.py`, `agent/repair_run.py`: the attempt counter is passed to each patch request.
- `evaluation/real_run.py`: every case now also writes `requests.jsonl` (one row per model request: stage, attempt index, hash of the exact messages, whether the prompt carries feedback and that feedback text, cache hit or live, tokens) and `repair.json` records `feedback_received` per attempt. Existing result folders do not have these files.
- Tests added: attempt index separates identical prompts; attempt-1 key unchanged and the field is never sent; replicates are independent and resumes reuse their own; every patch attempt carries its index; F1 attempts 2 and 3 carry the visible output (and never hidden text); F0 sends identical prompts but distinct attempts; F1 with no visible run gets no feedback (documented limit). Full backend suite: **687 passed, 23 skipped**; ruff check and format clean.
- Comparability: results produced before this change used the old key; their F0 attempts 2-3 are replays. Results after it use live attempts. The change cannot alter attempt 1 of any case.

### 11.5 New feedback experiment (24 Nov 2026), AxForge `glm-5.3-flash`, replicate 0, 1 worker, temperature 0
Cases fixed before running, from the variant group of dev 001 (`settings_default:shop_api:redis_host`, the only group where an edit once applied and failed visible tests): test 020, 040, 139 (official tier) and dev 001 (development tier). All four conditions ran on all four cases; no case was dropped after seeing results. Runs: `official-axforge-{L0,L1,G0,G1}-fb-test` and `dev-axforge-{L0,L1,G0,G1}-fb-dev`.

| Case | L0 | L1 | G0 | G1 |
|---|---|---|---|---|
| shop_api-020 | REJECTED (no_match x3) | same | same | same |
| shop_api-040 | REJECTED (no_match x3) | same | same | same |
| shop_api-139 | REJECTED (no_match x3) | same | same | same |
| dev shop_api-001 | REJECTED (no_match x3) | same | same | same |

- L0 and G0 were **live executions** (attempts 0, 1, 2 all live; prompts differ between L and G). **L1 and G1 were again cache replays of L0 and G0 (identical message hashes), because no attempt produced any visible-test output.** Verified in `requests.jsonl`: `has_feedback` is false in every request of every run.
- **Therefore feedback has still not been tested.** The mechanism is unit-tested to work; no real case has yet reached the point where it applies. Do not read L1 = L0 here as "feedback has no effect".
- Dev 001 on AxForge fails at edit matching, unlike BeatAPI, where its edit applied.

### 11.6 Needs your decision (not changed, because it would alter the methodology)
Feedback can only be exercised if attempts reach the visible suite. Options: (A) patch prompt shows the verbatim target file text for configuration targets (new prompt version, all conditions); (B) F1 additionally receives the edit-application error ("SEARCH did not match") when no visible output exists (changes the definition of F1); (C) choose cases whose first edit applies and fails visible tests (needs screening runs on more cases, about 20k tokens per case; selection must be fixed before seeing L1/G1 results). A is the most direct and fair; C leaves the prompt as is.

### 11.7 Usage after this work
- **AxForge:** 459,140 committed tokens (including 18,078 estimated for failed requests); remaining to the 2.4M ceiling **1,940,860**; 600,000 reserve untouched. This pass added 149,130 tokens, all in the L0 and G0 runs (the L1 and G1 runs used 0). No provider stop occurred.
- **BeatAPI (development ledger, separate):** 23 requests, 106,126 input and 32,892 output tokens.


## 12. Patch-generation fix (verbatim source files) and validated feedback path (24 Nov 2026)
Approved by the owner as Option A of section 11.6. This is a **pipeline correction**, not a methodology change: conditions L0/G0/L1/G1, temperature 0, three attempts per case, the visible-test feedback definition, the patch policy and the hidden-test rule are unchanged. Replicates (three, independent) remain a separate requirement; everything here is replicate 0.

### 12.1 Root cause of `no_match` (verified)
The patch prompt's target section for configuration diagnoses (`patch._code`) was the `config`/`compose` **evidence items**, truncated to 4,000 characters. Those items are rendered summaries made by evidence collection, for example `settings.redis_host [str] = 'redis-broker.internal'`. The real line in `lab/shop_api/app/settings.py` is `redis_host: str = "redis-broker.internal"`. The prompt told the model to copy SEARCH text from "the file shown", so it copied the rendered line, which exists nowhere in the file, and `apply_edits` correctly rejected it (`no_match`) every time, before any test ran. For code diagnoses the excerpt carried `N: ` line-number prefixes, so it also was not verbatim.

### 12.2 What changed
- `retrieval/sources.py` (`RealContextSource`): `source_files(case)` and `read_file(case, path)` return the **exact bytes decoded as UTF-8** (no newline translation, no line numbers) of editable source files only: under `lab/<the case's own service>/`, suffix `.py/.toml/.ini/.yaml`, not under `tests`, not `hidden_tests`/`.git`, no `..`, no drive letters, resolved path inside the repo. Everything else returns None (tests: other service, tests dir, `.env`, hidden tests, traversal, absolute path).
- `agent/patch.py`: the target section is now `<source_file path="...">` blocks with the exact file text. Files are chosen from the diagnosis only: its `path`, the paths of the evidence items it cites, then editable files of the service that mention the diagnosed name (at most 2 files). A file up to 8,000 characters is shown whole; a larger one only as contiguous verbatim windows (`lines="a-b"`) around the target. A short note states that `<source_file>` text is the real file and everything else (summary, `<evidence>`) is rendered or diagnostic. Context sources that cannot read files (sample sources in tests) keep the previous behaviour.
- `agent/prompts/patch_v4.md` (replaces `patch_v3` in `prompting.VERSIONS`): identical to v3 plus one sentence: only text inside `<source_file>` blocks is real file content; evidence lines are rendered summaries and must not be copied as SEARCH text. No other prompt component, no diagnose prompt, no tool, no temperature changed. `prompt_hash` therefore differs from all earlier records.
- Unchanged and still enforced: path allowlist, `apply_edits` exact unique matching, patch policy, sandbox, hash-bound records, hidden suite once on the frozen patch and never in a prompt. The gold fix (the reverse of the mutation patch) is not used anywhere in prompt construction; nothing is hardcoded per case.
- Kept from section 11: attempt-aware cache key, `requests.jsonl`, `repair.json` `feedback_received`.

### 12.3 Validation evidence (all eight requested points), dev case shop_api-001, L1, AxForge
Run `results/development/dev-axforge-L1-v4val-dev/cases/shop_api-001.r0/` (artifacts: `requests.jsonl`, `repair.json`, `patch.diff`, `run_meta.json`):
1. **The model receives real file text:** the patch request prompt contains `<source_file path="lab/shop_api/app/settings.py">` with the complete file (3,064 characters of target section; no-token dump for 001, 020, 040, 139 in the same form).
2. **SEARCH matches the real file:** the reply's SEARCH line `redis_host: str = "redis-broker.internal"` was found exactly once; all attempts in all new runs have empty `reasons` (before: `no_match` x3 everywhere).
3. **A legitimate patch applied:** `patch.diff` changes only `lab/shop_api/app/settings.py` (one line), within the allowlist, accepted by the policy.
4. **Visible tests executed after the patch:** `repair.json`: `visible_passed: false` for attempts 1, 2, 3 (the sandbox ran reproducer and visible suites; a failing reproducer is in the feedback).
5. **Feedback delivered:** attempt 2's prompt contains `<visible_test_feedback>` with the actual reproducer/visible output of attempt 1 (checked: the stored `feedback_received` equals the text inside the prompt).
6. **Genuinely new requests:** attempts 2 and 3 are `cache_hit: false` live requests (attempt indexes 1 and 2; the prompt hash of attempt 2 differs from attempt 1 because of the feedback).
7. **No hidden or gold exposure:** no request row mentions "hidden"; the hidden-leak guard checked every request (`hidden_guard_calls` 5); a scan of all 135 cached provider requests found no hidden-suite test name (22 checked), no `mutation.patch`, no "gold".
8. **Policy and safety intact:** the diff touched one allowed file; hidden suite ran once at the end (0 passed, 3 failed: the patch is wrong, not blocked).
Unit tests prove the same properties on controlled repositories (section 12.5).

### 12.4 Controlled feedback experiment after the fix (replicate 0, AxForge `glm-5.3-flash`, temperature 0, 1 worker)
Same four cases as section 11.5 (test 020, 040, 139 under `official-axforge-{L0,L1,G0,G1}-v4fb-test`; dev 001 under `dev-axforge-{...}-v4fb-dev`). All conditions on all cases; nothing dropped.

| Case | L0 | L1 | G0 | G1 |
|---|---|---|---|---|
| 020 | REJECTED (visible_failed, 3 attempts) | same | same | same |
| 040 | REJECTED | same | same | same |
| 139 | REJECTED | same | same | same |
| dev 001 | REJECTED | same | same | same |
- Every attempt applied and ran the visible suite. **In L1 and G1 attempts 2 and 3 carried feedback (`has_feedback` true, 2,000 characters of visible-test output) and were live requests; in L0 and G0 no attempt carried feedback.** Attempt 1 of L1/G1 is a cache hit of attempt 1 of L0/G0 (byte-identical prompt, valid reuse).
- **Every condition produced the same final patch: `redis_host: str = "lab_redis"`** (the correct value is not `lab_redis`; hidden suite 0 of 3 passed in every run). Neither the graph context (prompts differ between L and G) nor the feedback changed the patch in these 4 cases, and F0 retries returned the same reply as attempt 1. **No feedback effect and no graph effect was observed in this sample; 4 cases of one fault family and replicate 0 cannot support any conclusion about either factor.**
- Reuse in these runs: L0 shop_api-020 attempts 1 and 2 were served from the cache because the run was interrupted by an AxForge HTTP 429 at its start and resumed after 300 s (calls already completed before the stop are reused, as before). Dev 001 L1 is a full replay of the validation run `dev-axforge-L1-v4val-dev` (identical inputs). Both are valid reuse and labelled here; the 429 left no record (artifacts in `cases/shop_api-020.r0.provider_error.*`).
- Observations, not changed: the feedback is cut to its first 2,000 characters (`FEEDBACK_CAP`, existing), which for these failures is mostly the start of the traceback (a name-resolution error), and F1 attempts 2 and 3 can see identical feedback when the patch is identical.

### 12.5 Tests and comparability
- New `tests/agent/test_verbatim_source.py` (22 tests) and additions to `test_gateway.py`, `test_repair_run.py`: exact bytes and CRLF; refusal of tests, other services, secrets files, traversal, hidden tests, absolute paths and missing files; prompt shows file text and keeps evidence labelled as evidence; large-file windows are contiguous and exact; at most 2 files; fallback for sources without file access; SEARCH copied from the prompt applies and the visible suite runs; SEARCH copied from the rendered evidence still fails `no_match`; an edit outside the allowed files is rejected before any test; F1 attempt 2 gets the real visible output as a new request and F0 gets none; cache keys separate attempts, replicates and different inputs; hidden text never appears in prompts or logs.
- Full backend suite **710 passed, 23 skipped**; `ruff check` and `ruff format --check` clean. No frontend code was touched, so frontend tests were not run.
- **Comparability:** results before this section used `patch_v3` and rendered evidence (and, before section 11, the old cache key). Their patch stage is not the same experiment as the new one; do not pool them. New results are marked by run ids containing `v4`, prompt hash of `patch_v4`, and the presence of `requests.jsonl`. No old result was changed. The diagnose stage is unchanged, so its cached responses were legitimately reused.

### 12.6 Usage
- **AxForge:** 601,223 committed tokens (18,078 estimated for failed requests included); remaining to the 2.4M ceiling **1,798,777**; 600,000 reserve untouched. This task used 142,083 tokens (validation run about 10.3k, the v4 experiment the rest; L1/G1 attempt-1 and dev-001 replays cost 0).
- **BeatAPI (separate ledger):** unchanged, 23 requests, 106,126 input / 32,892 output tokens; no BeatAPI run was needed (the development G0 run for 001-003 was already complete).


## 13. Case screening for feedback (24 Nov 2026), patch_v4 only - stopped at a safety-guard blocker
All runs here use `patch_v4`, AxForge `glm-5.3-flash`, temperature 0, replicate 0, 1 worker, official tier (test split). They are not comparable with `patch_v3` results (sections 7, 9, 10) and are not pooled with them. Replicates (3) are not run; the replicate requirement is **not** met.

### 13.1 Frozen lists (written before any model call; files in `results/screening/`)
- **List A** `v4-screening-frozen.json` (sha256 `16adb24e4c2737fa1e0af0507ab57cb212aaf5fbb2063536d089479c1272c2b1`). Rule, from manifest metadata only: patchable classes only (configuration, application_code; the runtime-dependency and insufficient-evidence classes are abstention classes by design, no patch is expected); exclude every case already run in any earlier experiment and shop_api-035; four strata (service x cause class); in each, the first two cases by id with a distinct fault family and variant group. Cases: shop_api-015 (wrong_value, shipping_fee), 016 (wrong_unit, tax_rate), 018 (wrong_argument, ship_base), 022 (missing_cap, discount_cap), 021 (worker, queue_name_mismatch), 023 (worker, wrong_value max_retries), 049 (worker code, wrong_argument retry_budget), 054 (worker code, wrong_queue). Eight fault families, no Redis case.
- **List B** `v4-screening-B-frozen.json` (sha256 `4a5ab832a31d547afe2b9b0a65029b887ce7ea696027b95bbeeff6c28e4c5c6f`), frozen after list A produced nothing: cases whose diagnose-stage output in the earlier pilot already reached a patchable diagnosis (a necessary condition for any patch to exist; no patch, visible-test or hidden-test outcome was used): shop_api-006, 010, 013.
- Suitability criteria (fixed beforehand): first attempt applied and the visible suite ran; it failed at least one test; its test output is non-empty; a gold fix exists (frozen dataset validation).

### 13.2 Stage 1 outcomes (condition L0), every attempted case
| Case | Gold class | Diagnosis | Result | Suitable |
|---|---|---|---|---|
| 015, 016, 022 | config, config, code | insufficient_evidence (6-tool budget used without a diagnosis) | NO_PATCH `budget_exhausted` | no |
| 021, 023, 049, 054 | config, config, code, code | insufficient_evidence (abstained) | NO_PATCH | no |
| 018 | code | configuration (wrong class) | NO_PATCH `output_truncated` (patch reply hit the output cap with no content) | no |
| 006 | code | configuration (wrong class) | NO_PATCH `output_truncated` | no |
| **010** | code | configuration (wrong class) | attempt 1 **applied**, visible suite ran: reproducer 0 passed / 2 failed, visible 34 passed / 1 failed; attempt 2 (F0, a live request): `output_truncated` | **yes (the only one)** |
| 013 | config | application_code (wrong class) | attempt 1 applied, reproducer 1/1 and visible 35/35 passed, hidden failed: REJECTED `hidden_failed` | no (first patch passed visible) |
Under `patch_v3` 013 was TEST_VERIFIED_IN_LAB; under `patch_v4` its first patch fails the hidden suite. The two are different experiments and the difference is reported, not explained away.
**Counts: 11 cases screened; 1 suitable (010); 1 first attempt applied and failed visible tests; 0 improved.**

### 13.3 What blocked the screening
1. **Seven of eight list-A cases never reach the patch stage:** the agent abstains or exhausts its tool budget. Configuration and code cases have no trace frames in their evidence, so diagnosis is hard for this model. This, not the patch pipeline, is why feedback opportunities are rare.
2. **Truncated patch replies (3 of the 5 patch requests made in the screening: 018, 006, and 010 attempt 2):** the reasoning model spends the whole output cap on hidden reasoning (`finish_reason` length, no content). Raising `llm_max_output_tokens` would be a model-setting change for all conditions, so it was not made; **this needs your decision**.
3. **A harness bug found and fixed (technical, tested):** a truncated patch reply was recorded as a provider outage, so the run stopped with no record, and every resume replayed the cached truncated reply (case 018 stalled three resumes with no tokens used). `repair_run` now records it as `NO_PATCH` with `failure_reason: output_truncated`, the same label `request_patch` already used; real provider failures are still `provider_error` and still stop the run. Tests added for both.
4. **The hidden-test leak guard blocked F1 on case 010 (not fixed; needs your decision).** L1 and G1 on 010 (runs `official-axforge-L1-v4scrB-test`, `official-axforge-G1-v4scrB-test`) each ended as a record `UNVERIFIED` with `pipeline_crash: AssertionError: hidden-test material 'test_price_1' found in a model prompt`, 0 tokens, no request sent, no case artifacts. The guard flags every test name in the hidden suite. `test_price_1` is also the name of the visible reproducer test (shared by design, section 1), and the reproducer's failure output, which is the F1 feedback, necessarily contains it. So the guard prevents F1 for any case whose reproducer shares a name with the hidden suite. The guard did its job (nothing was sent); I judged narrowing it (exclude names that occur in the case's own visible test files; keep hidden-only names, hidden file names and paths blocked) to be a change to a safety control, an edit to it was refused by the permission layer, and I stopped. These two records stay as history and must not be counted as L1/G1 results. G0 on 010 completed from cache and reproduced L0 (the graph context is identical for 010: same message hashes for the diagnose calls), so it adds no information.

### 13.4 Whether feedback has been shown to help
**No.** In this screening, no F1 attempt was delivered on a screened case (blocked as in 13.3). In the earlier v4 experiment (section 12.4, 4 Redis-family cases) feedback was delivered live in 8 L1/G1 runs and the final patch was unchanged in every one. So there is no measurable evidence that feedback improves repairs, and also not enough evidence that it cannot.
**Graph vs lexical evidence:** differences were measured without model calls: context identical on 9 of 12 earlier cases and different where trace frames exist (001, 003, 007) and on the Redis-family cases; on 010 identical. Graph outcomes differed from lexical outcomes in none of the runs so far.

### 13.5 Usage
AxForge: 837,933 committed (18,078 estimated for failed requests included); remaining to the 2.4M ceiling **1,562,067**; reserve untouched. This phase used 236,710 tokens: list A 218,186, list B 18,524. BeatAPI (separate ledger): unchanged, 23 requests, 106,126 in / 32,892 out. Provider interruptions: several HTTP 429 stops at the start of list A (rounds 1-2 used no tokens; recovered after pauses). Incomplete runs: none (all records exist), but L1/G1 for 010 are crash records, not results.


## 14. Guard narrowing, patch cap 8192 and 010 validation (24 Nov 2026) - INCOMPLETE
Changes (uncommitted, interim; superseded by the v5 proposal in `pipeline-v5-architecture-plan.md` if approved): (a) `HiddenLeakGuard` takes optional `visible_dirs`; hidden test names that are also defined in the case's own visible test files (reproducer dir, `lab/<service>/tests`) are exempt and listed in `shared_visible`; hidden-only names (e.g. `test_price_3`), hidden file names and `hidden_tests` stay blocked (4 new tests). (b) Patch-stage output cap 4096 -> 8192 for every condition and attempt (`PATCH_MAX_OUTPUT_TOKENS`; diagnose cap unchanged, so diagnose cache entries still hit). (c) Truncated empty replies are no longer cached and a previously cached one is treated as a miss (2 new tests). Suite: 720 passed, 23 skipped before the last fixture edit; ruff clean.
Validation run `official-axforge-L0-v4cap8k-test` (010, L0) did **not** complete: no record. Live patch attempt 1 used 7,688 output tokens (cap 8192, applied, reproducer 0/2 passed, visible 34/1 failed); attempt 2 used 2,290 (a different patch, same visible result, F0 so no feedback); attempt 3 failed with HTTP 504 (earlier rounds: 429, unreachable). The supervisor stopped after 3 rounds without a record. These are `provider_error` artifacts, not results. G0/L1/G1 were not run, so feedback delivery under the narrowed guard is **not yet validated**. Finding: a ~100-token patch cost 7,688 tokens, so raising the cap hides the reasoning overrun rather than fixing it. AxForge used in this task: 19,022 tokens (ledger 856,955 committed, 1,543,045 remaining).

### 14.1 Update: resumed validation of 010 (24 Nov 2026)
- `official-axforge-L0-v4cap8k-test` **completed** (REJECTED `visible_failed`, 3 attempts, hidden failed; diagnosis `configuration shop_api.DB_HOST`, wrong class as before). All three attempts applied and ran the visible suite (reproducer 0/2 passed, visible 34 passed / 1 failed each), with **three different patches** (diff sha 3b8096.., f9ecbd.., 6b7838..) from **identical prompts** (same message hash, no feedback): the provider is not deterministic at temperature 0 for patch attempts, so a changed patch after feedback is not by itself evidence that feedback was used. Output tokens: 7,688 / 2,290 / 1,254 (no truncation at the 8192 cap, but attempt 1 came within 504 tokens of it).
- `official-axforge-G0-v4cap8k-test` completed as a **cache replay** of L0 (graph context identical for 010; same message hashes): it adds no independent information.
- `official-axforge-L1-v4cap8k-test`: attempt 1 replayed from L0's cache; the attempt-2 request carried 2,072 characters of visible reproducer/suite output including `test_price_1`/`test_price_2`, **passed the narrowed guard** and was sent, then failed at the provider in 6 consecutive rounds (429, unreachable, 504, 504, 502, 429; six `provider_error` artifacts, no record). So the guard fix is verified to let legitimate feedback through, but feedback has **not** produced a model response, and no improvement or change can be claimed. G1 was not run (it would replay L1).
- AxForge: 872,241 committed (including conservative estimates for failed requests), 1,527,759 remaining; reserve untouched. Used since the 8192-cap change: 34,308. Hypothesis (unverified): the 504/502 are gateway timeouts on long reasoning requests, which the 8192 cap makes more likely.


## 15. dev-d1 / pipeline v5: implementation and first smoke stage (24 Nov 2026) - DEVELOPMENT TRACK, not the formal experiment
Implemented per `diagnosis-root-cause-report.md`; components, files and isolation rules are in `dev-d1-configuration.md`. Formal v4 behaviour, condition definitions and the frozen test split are unchanged; v5 runs are development tier, dev split, live requests only (cache disabled), and the runner refuses unsafe combinations. Frozen plan and criteria: `results/screening/v5-level1-frozen.json` (written before any model call; updated with the owner's approved batch).

**Smoke stage (owner-approved): L0 only, diagnose-only, one case per independent site, run `results/development/dev-axforge-L0-dd1-smoke`.** Not the Level-1 gate; one arm cannot say anything about graph vs lexical.
| Case (site) | Diagnosis | Class | Exact function | Tool calls | Tokens in/out |
|---|---|---|---|---|---|
| shop_api-014 (stock_decrement) | application_code `inventory.py::reserve` | correct | correct | 1 | 7,121 / 484 |
| shop_api-058 (tax_base) | application_code `quote.py::quote` | correct | correct | 3 | 15,169 / 2,837 |
| shop_api-096 (total_loop) | application_code `orders.py::order_total` | correct | correct | 2 (+1 rejected submission, not counted) | 24,289 / 1,066 |
Total 50,966 tokens (ledger 872,241 -> 923,207; 1,476,793 remaining to the 2.4M ceiling; reserve untouched). No provider failure, no cache hit (6 live requests: 1, 2 and 3 per case), no patch request, guard raised nothing (1/2/3 calls screened).
- Symptom collected and sent: baseline reproducer and visible suite run on the base commit (counts: 014 repro 0/2, visible 34/1; 058 0/2, 33/2; 096 0/2, 27/8); each model cited only SYMPTOM evidence items and quoted symptom values (e.g. 11.95 vs 11.10), which shows the symptom reached it. Every cited id exists.
- Retrieval (L arm): the faulty function was in the retrieved context at rank 9 (014), 6 (058), 10 (096) of 21/20/25 hits (offline evaluation only). Before the change the v4 query put none of them in the context (offline check on these dev cases).
- Caveats: (1) the visible test names and endpoints in the symptom contain the gold function name (offline gold-term audit: 'reserve', 'quote', 'order_total'); this is permitted visible-suite output, but it means Level 1 with a symptom is an easier task than blind diagnosis and must be remembered when interpreting scaling. (2) self-reported confidence was `low` for two correct diagnoses, so confidence is not a usable signal (it is not used for gating). (3) the reason for the one rejected submission in 096 was not recorded (fixed: rejected calls now keep their error text in trace.json); (4) there is no v4 diagnosis run on these three cases, so no valid diagnosis-level before/after exists yet; (5) 3 cases at temperature 0 are one sample each.
Status: stage S0 complete; full six-case L0+G0 evaluation and the controls are waiting for the owner's review.

### 15.1 Six-case L0/G0 evaluation: HALTED on provider failure (24 Nov 2026)
Run `dev-axforge-L0-dd1-l1` (dev-d1, diagnose-only, live requests): shop_api-014 completed (record written); shop_api-058 failed twice with HTTP 429 (the first after one successful request of its own diagnosis; the second, after a 5-minute pause and one resume, at the first request). Both attempts are kept as `provider_error` artifacts (`cases/shop_api-058.r0.provider_error.*`): they are **not results**. The remaining L0 cases (096, 182, 067, 085), all G0 runs and the controls were not run. Policy followed: halt on the first failure, one resume after a pause, then stop. Ledger 938,183 committed (1,461,817 remaining); this evaluation so far used 14,976 tokens (the two requests of 014).


## 16. Operating strategy and defects found while AxForge was unavailable (24 Nov 2026)
Documented in `dev-operating-strategy.md`; the cross-provider experiment is only a proposal (`cross-provider-evaluation-design.md`, not approved, not run). No model request was made for this work.
Defects found by local inspection and fixed (all development-track; the formal pipeline is unchanged):
1. **Run-level `meta.json` of dev-d1 runs said `tier: official` and carried the v4 prompt hash** (per-case `run_meta.json` was correct). Fixed in `run_experiment` (tier is development for pipeline v5; v5 prompt hash; `pipeline_version`, `diagnose_only`, `dev_config` recorded) and corrected in place for the two existing runs, `dev-axforge-L0-dd1-smoke` and `dev-axforge-L0-dd1-l1`, keeping the original values under `meta_correction` (their case records and artifacts are untouched).
2. **A resumed run could change provider/model/pipeline silently** (only dataset/condition/split were checked). Now refused with `run_id exists with a different provider/model/pipeline` (tested).
3. **The AxForge ledger labelled all spend official.** `usage_report` now attributes spend to run ids and splits `development` from `official_or_unattributed`: 168,238 development tokens (of which dev-d1: smoke 50,966 and `dd1-l1` 14,976) and 769,945 other, total 938,183.
4. **Symptom text was not byte-stable**: pytest prints object memory addresses (`<Product object at 0x7dfb...>`), so two runs of the same case sent prompts that differed by a token and an L0/G0 pair would not have received identical symptoms. Addresses are now normalised (`0x...`; tested). The preserved shop_api-014 L0 record (`dev-axforge-L0-dd1-l1`) was produced before this fix: its prompt contains the raw address, a cosmetic one-token difference from the prompt the G0 arm will receive; noted, not hidden.
New tests: `tests/evaluation/test_diag_eval.py` (scorer: metrics, retrieval ranks/overlap/unique hits, identifier-exposure vs source-reasoning indicators, unsupported claims, abstention, summary by site, real 014 artifacts), runner resume/binding/tier tests, usage attribution test, symptom stability test.
Saved 014 artifacts (two independent live L0 samples, smoke and `dd1-l1`): both exact (`inventory.py::reserve`), 1 vs 2 tool calls, different self-reported confidence (low vs high); the second sample is the preserved evaluation result.

### 16.1 Resume attempt of the controlled evaluation (24 Nov 2026): FAILED again, HTTP 429
One invocation of `bash scripts/dd1_l1_eval.sh` (ledger verified first: 938,183 committed, 1,461,817 remaining, reserve intact) ran `dev-axforge-L0-dd1-l1`: shop_api-014 stayed as it was (record kept); shop_api-058 failed with HTTP 429 at its first request (third `provider_error` artifact, `cases/shop_api-058.r0.provider_error.1795510362`); the script stopped (`STOP incomplete`). No tokens were charged (ledger unchanged), no provider switch, no retry loop. Finding (corrected, see `axforge-pacing-audit.md`): the invocation reached the network **once** (one 429 row per invocation in the ledger); the three rows in the artifact's `requests.jsonl` were three diagnose-loop calls, the second and third refused locally by the per-process halt. An earlier version of this note said three requests were sent; that was wrong. For dev-d1 (v5) the loop now stops at the first failed request; v4 keeps its tolerance. Remaining: L0 for 096, 182, 067, 085 and 058, all G0, the controls. AxForge has now returned 429 on every attempt since about 13:30.
Added: `evaluation/fingerprint.py` (code fingerprint recorded in v5 `run_meta.json`) and a raw-address flag in the scorer, for exact reuse audits; the reuse audit and decisions are in `cross-provider-evaluation-design.md`.


### 16.2 AxForge pacing enforced: 2 RPM, shared (24 Nov 2026)
Audit and changes in `axforge-pacing-audit.md`. Before: the limit was 10 s from the previous **completion**, in process memory (not shared across processes or resumes; the first request of every process waited zero). Now: at least 30 s between request **starts**, machine-wide (OS lock plus `runs/axforge_pacing.json`), one request in flight, 429 stops the run and records status/time/redacted headers/Retry-After, and a later attempt is refused until Retry-After elapses. No request was made; BeatAPI is unchanged.


## 17. dev-d1 Level-1 diagnosis evaluation: COMPLETED (24 Nov 2026) - development track, diagnose-only, AxForge glm-5.3-flash
Runs: `dev-axforge-L0-dd1-l1` (6 cases; 014 is the preserved earlier result, the others ran after the pacing change), `dev-axforge-G0-dd1-l1` (6), controls `dev-axforge-{L0,G0}-dd1-ctrl` (004, 001). One invocation of `scripts/dd1_l1_eval.sh`, 23 live requests, no 429 and no provider failure, no patches, no hidden tests, no feedback. Scored with `diag_eval.py` (`results/development/dd1-l1-evaluation.json`); the criteria are those frozen in `results/screening/v5-level1-frozen.json`.
**Level 1 (6 cases, 3 independent sites).** L0: class 6/6, file 6/6, exact function 6/6, abstentions 0, unsupported claims 0. G0: identical, 6/6 on all. Per site (each with 2 variants): total_loop 2/2 and 2/2, stock_decrement 2/2 and 2/2, tax_base 2/2 and 2/2; independent sites with a correct function: 3/3 in both arms. Criteria (class 6/6, function >=5/6 and at least once per site at both arms, abstention <=1/6, 0 unsupported claims): **met for the diagnosis stage**. The patch and feedback criteria were not evaluated (not run).
**Retrieval (offline).** The faulty function was in the prompt in all 12 runs. Rank in the retrieved list L vs G: 014 9 vs 4, 067 9 vs 4, 058 6 vs 4, 085 5 vs 4, 096 10 vs 6, 182 6 vs 6 (G higher in 5 of 6, equal in 1). G rendered less context (95 chunks / 40,477 chars vs 135 / 56,101 over the six cases). Unique G hits (13 source/test chunks over six cases, from symptom anchors and graph expansion) contained no gold-file chunk that L lacked (the gold function was already in L's list); every retrieved hit scores "relevant" under the symptom-term/anchor measure, so that measure does not discriminate and says nothing about usefulness.
**Cost and behaviour (six L1 cases):** L0 89,680 tokens, 12 tool calls, 11 requests, 474 s of model time; G0 66,116 tokens, 12 tool calls, 9 requests, 226 s. One rejected submission in L0 (182: `observed_symptom` over 200 characters, corrected on the next call, correctly not counted against the budget). Confidence was self-reported low in 7 of 12 correct diagnoses.
**Validity limitations.** (1) The gold function name is exposed by the visible symptom in 12/12 runs (test names/endpoint); in 10/12 runs the rationale also quotes the faulty line itself (source reasoning), in 2 it does not (067 G0, 085 G0). (2) One sample per cell; the model is not deterministic at temperature 0 (014 gave 1 and 2 tool calls in two samples), so the differences in tokens/calls between arms are within what one extra sample can change. (3) Strict pairing holds for 5 of 6 cases (identical symptom text in L0 and G0); **014 is near-paired**: its preserved L0 symptom contains an object address that the G0 symptom has normalised (cosmetic one token). (4) 3 independent sites, dev split.
**Controls (not in the L1 denominator).** 004 (intermittent, no failing test: symptom status `no_failure`): both arms abstained (`insufficient_evidence`), as expected. 001 (Redis host default, reproducer fails): both arms diagnosed `shop_api.REDIS_HOST` correctly. They show the pipeline abstains when no test fails and still finds a connectivity/config cause when the evidence supports it; the scorer's file metric is not meaningful for config keys.
**What this does and does not show.** dev-d1 diagnosed all Level-1 cases correctly in both arms, with the symptom and visible test names in the prompt. It does **not** show that graph retrieval improves diagnosis (identical outcomes; both retrieved the gold function; G ranked it higher and used a smaller context), and the exposed identifiers mean the task is easier than blind diagnosis.
Tokens: this evaluation used 176,589 (ledger 938,183 -> 1,114,772; 1,285,228 remaining to the ceiling; reserve untouched).


## 18. dev-d1 Level-1 PATCH stage: COMPLETED (24 Nov 2026) - development track, F0 (no feedback), AxForge glm-5.3-flash
Runs `dev-axforge-L0-dd1-patch` and `dev-axforge-G0-dd1-patch` (six cases each), launched as audited (`dd1-patch-stage-plan.md`) with `scripts/dd1_patch_eval.sh`: saved diagnoses and evidence loaded from the frozen runs (manifest verified before and after, 251 files unchanged), no diagnose request (0 in every run), 12 live requests, no 429, no provider failure, 700k floor not approached. Scored with `patch_eval.py` (`results/development/dd1-patch-evaluation.json`).
| Metric (separate) | L0 | G0 |
|---|---|---|
| Diagnosis correct (from the frozen diagnosis stage) | 6/6 | 6/6 |
| Patch generated | 6/6 | 6/6 |
| Patch applied | 6/6 | 6/6 |
| Reproducer passes | 6/6 | 6/6 |
| Visible suite passes | 6/6 | 6/6 |
| Hidden suite passes (counts 3 of 3 each) | 6/6 | 6/6 |
| Fixed (reproducer + visible + hidden) | 6/6 | 6/6 |
| Visible-suite regressions | 0 | 0 |
| Attempts | 1 each | 1 each |
Per independent site: total_loop 2/2 and 2/2, stock_decrement 2/2 and 2/2, tax_base 2/2 and 2/2 (3 of 3 sites fixed in both arms).
Every patch changes exactly one line in one file (the diagnosed file), inside the gold function, and is **identical to the reverse of the mutation** (exact gold-equivalent 12/12); no scope-policy rejection, no retry, no feedback. Baseline visible runs on the base commit had 1 to 8 failing tests (e.g. 096: 27 passed, 8 failed); after each patch all 35 visible tests pass, so nothing that passed at base failed afterwards. Hidden-suite regressions are reported only as counts (0 failed of 3).
Cost: L0 24,419 tokens (24,223 in, 196 out), G0 24,381 (24,185 in, 196 out), 48,800 in total (ledger 1,114,772 -> 1,163,572; 1,236,428 remaining). Output was 27 to 43 tokens per patch. Record latency (model + sandbox) 18 to 26 s per case, 145 s (L0) and 148 s (G0) per run of six. Pacing: the new send-time log shows 12 request starts with every start-to-start interval exactly 30.0 s (min = median = max), i.e. the 30 s limit held.
**Interpretation limits.** (1) The diagnoses already name the faulty line and the fix, and the verbatim file is in the prompt, so each patch is essentially a mechanical consequence of the diagnosis; this stage shows the patch/apply/verify machinery works on these cases, not independent repair skill. (2) The patch prompt does not contain retrieval context, so L0 vs G0 here differ only through their (both correct) diagnoses: no graph effect can be read from it. (3) The scope policy, retries and the 3-attempt loop were not exercised (all first attempts accepted and verified), and feedback was not run by design. (4) One sample per cell, 3 independent sites, dev split; the symptom exposes the gold function name. (5) Hidden-suite regressions cannot be listed by name.


## 19. Final evaluation (RC1, staged subset of the frozen test split): COMPLETED on AxForge key 1 (24 Nov 2026)
Full report: `final-evaluation-report.md`. 12 selected test cases (blind seeded draw, one per variant group), replicates 0 and 1 on all 12 and replicate 2 on 8 (pre-declared seeded subset), conditions L0/G0/L1/G1 with shared diagnosis for the feedback pairs; 128 case-runs, 239 requests, 0 provider failures, 1,592,050 tokens (ledger 1,255,286 -> 2,847,336 of 3,000,000). Fixed: L0 25/32, G0 26/32, L1 25/32, G1 26/32; code faults 16/16, configuration 9/10 (L0) and 10/10 (G0), abstention 3/3, runtime-dependency class 1/3 (L0) and 2/3 (G0); no first-attempt failure anywhere, so feedback was not exercised. This is a reduced protocol (12 of 151 cases; 2 full replicates plus a reduced third); it does not complete the original design.
