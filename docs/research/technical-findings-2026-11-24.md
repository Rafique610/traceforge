# TraceForge technical findings (24 Nov 2026): experiment, embeddings, failures, improvement plan

> **Correction note, 2026-11-25 (no result changed).** The correct replicate coverage of the whole RC1 evaluation in `results/final` is: replicate 0 on all **35** sites, replicate 1 on **12** sites, replicate 2 on **8** sites (23 sites have replicate 0 only). Earlier wording such as "12 sites with replicates 0 to 2" describes stage 1 only and over-states replicate 2 (8 of the 12 sites). This is a reduced evaluation, not the A3-protocol deliverable (L0 vs G0 on at least 50 cases); no claim that G1 or the graph arm is superior is established.

Investigation only: no model requests, no frozen condition, record or result was changed. Companion documents: [failure-analysis.md](failure-analysis.md) (every non-verified case-run, `results/analysis/failure_cases.csv`), [retrieval-embeddings-investigation.md](retrieval-embeddings-investigation.md) (code trace and offline retrieval scoring), [final-evaluation-report.md](final-evaluation-report.md) and [final-evaluation-stage2.md](final-evaluation-stage2.md) (results). Coverage data: `results/analysis/coverage_matrix.csv`.

## Key findings
1. **There are no embeddings anywhere in TraceForge.** No embedding code, no vector column, plain `postgres:16`. Retrieval is BM25 (rank-bm25 Okapi, custom identifier-aware tokenizer) over graph-derived code chunks, plus, for the G arm, symptom-derived graph anchors and a 2-hop graph walk.
2. **"35/35 verified fixes" is not attainable by design.** 6 of the 35 sites are non-repairable (3 insufficient-evidence, 3 runtime-dependency): the correct behaviour is to abstain, so the ceiling is 29/35. On the 29 repairable sites replicate 0 reached **G0 28/29 and L0 27/29 (L1 28/29, G1 29/29)**. The only 4 genuine repair failures in the whole record (4 of 180 repairable case-runs, over all replicates) come from two stage-2 configuration cases and none is due to retrieval, patch scope/guard policy or validation.
3. **The two real failure causes are cheap engineering defects, not retrieval problems:** (a) the diagnosis tool's 500-character `rationale` limit rejects the model's submission (8 case-runs, 2 of them genuine failures on `shop_api-019`, 6 on the non-repairable `shop_api-030`); (b) without feedback the patch loop repeated the identical wrong value three times (`shop_api-020`, `"lab_redis"`), which feedback repaired (`"localhost"`).
4. **Statistically the evidence is thin:** 35 sites, one replicate for 23 of them. Nothing supports "graph beats lexical" or "feedback improves performance"; see section 6.
5. **Any change made in response to these failures requires a new release candidate and must not be validated on the cases that motivated it** (section 7).

## 1. The experiment
**Shared by all four conditions:** the same model (AxForge `glm-5.3-flash`, temperature 0), the same evidence (visible-test symptom, labelled evidence items, deterministic diagnostics findings), the same `diagnose_v2` prompt and tool budget (8 calls), the same patch prompt, scope policy, guard and approval rules, up to 3 patch attempts, and a hidden suite that runs once on the final patch and is never shown to the model.

| Condition | Retrieval arm | Feedback | Runs |
|---|---|---|---|
| **L0** | L: lexical (BM25) over graph-derived chunks | none | full run: diagnosis, then up to 3 patch attempts; attempts 2 and 3 see only their own earlier edit, not test output |
| **G0** | G: L plus graph retrieval | none | full run |
| **L1** | L | visible-test feedback on attempts 2 and 3 | patch stage only, started from L0's saved diagnosis |
| **G1** | G | visible-test feedback on attempts 2 and 3 | patch stage only, from G0's saved diagnosis |

- **L versus G** differs only in retrieval: G adds symptom-derived graph anchors (tests, routes, config keys named by the symptom), a walk of up to 2 hops from the anchors, expansion and proximity/test-link score terms. Corpus, query, packer (3000-token context budget, 80% usable) and the agent tools are shared.
- **0 versus 1** differs only in whether failed attempts' visible test output (test ids and assertion text, never hidden tests) is shown to the next attempt. Because feedback acts only after a first patch fails, L1/G1 reuse the diagnosis of L0/G0; their diagnoses are identical by construction (checked on all 55 case pairs). L1 is therefore not an independent run of L0 but a paired continuation, and L1 can only differ from L0 where L0's first attempt failed.

**Replicates.** The model is a reasoning model, not deterministic even at temperature 0 (cases flip between replicates in our own data: e.g. `shop_api-030`, `-019`). One replicate cannot separate "the method failed here" from "this sample was unlucky"; three replicates give a within-case variance estimate and the formal design requires them.

**Coverage (X = record exists; cells are L0 G0 L1 G1).** 220 of 420 cells exist; 200 are missing: stage-1 replicate 2 for four cases (16 cells), and replicates 1 and 2 for all 23 stage-2 cases (184 cells).

| | r0 | r1 | r2 |
|---|---|---|---|
| Stage 1 (12 sites) | 12 sites complete | 12 complete | 8 complete; missing for 047, 100, 148, 181 |
| Stage 2 (23 sites) | 23 complete | not run | not run |
| Total cells | 140/140 | 48/140 | 32/140 |

Full case x condition x replicate matrix: Appendix A.

## 2. Embeddings: verified from the code
- **Not used anywhere.** There is no embed/vector/faiss/chroma/pgvector code and no vector type in the migrations; the database image is plain `postgres:16`; the `openai` SDK is used only for `chat.completions`. Embeddings appear only as an optional idea in planning documents. So no embedding model, provider or dimension exists and none is used by L0, G0, L1 or G1 (evidence: retrieval-embeddings-investigation.md, section A).
- **What runs instead (both arms):** BM25 Okapi (`rank-bm25`) with an identifier-aware tokenizer over graph-derived chunks, top 50; the query is built from the service name, log/trace signal lines, frame names and symptom terms (`anchors.py`). **G additionally:** graph anchors, a bounded graph walk and proximity/test-link/uncertainty score terms (`retrieve.py`, `graph_ranker.py`). No BM25-plus-embedding fusion exists.
- **Installed tooling:** Ollama 0.40.17 with `all-minilm:22m` (a 384-dimension sentence model) is in the local model store, but the server timed out when queried, so runtime availability is unconfirmed; the backend venv has neither torch nor sentence-transformers.

## 3. Would hybrid retrieval help? What the data say, and how to test it
**Offline measurement on the saved artifacts** (29 repairable sites, replicate 0; gold used for scoring only):
| | L | G |
|---|---|---|
| gold region in the context actually sent | 23/29 | 24/29 |
| mean gold recall in sent context | 0.69 | 0.72 |
| mean reciprocal rank (sent) | 0.14 | 0.23 |
| precision (sent chunks overlapping gold) | 0.039 | 0.058 |
| mean context tokens sent | about 2,336 | about 1,712 |
Application code: recall 0.85 (L) vs 0.90 (G). Configuration: recall 0.33 for both arms (the gold is a settings key and the chunk overlap measure is weak for it, 6 of 9 sites). Retrieval latency is not recorded per arm, so no latency comparison is possible.

**Reading it.** Gold was missing from the sent context for 6 (L) and 5 (G) sites, yet in 5 of 6 (L) and 5 of 5 (G) cases the diagnosis was still exact (the symptom, visible test names and evidence already point at the function). Retrieval quality and diagnosis success are weakly coupled in this dataset, and precision is low for both arms (the packer fills a fixed budget). So (a) a hybrid arm has room to improve **recall at low rank and precision**, and G already does somewhat better than L on rank and token use; (b) it has little room to raise end-to-end success on this benchmark, where almost every repairable site is already fixed; (c) semantic embeddings could add regions that lexical and graph retrieval miss only if such regions exist: that is testable offline for free (below), and is **not known today**.

**Valid evaluation without contamination (no LLM tokens for stage 1):**
1. Build the benchmark on the **dev split** (33 cases), never the frozen test split: retrieval only, gold used for scoring only.
2. Arms: lexical, graph, embedding-only, and a reciprocal-rank fusion of the three (new names H0/H1 for any later end-to-end arm; new run directories; frozen L/G artifacts untouched).
3. Metrics: recall@k, precision@k, MRR, nDCG, gold-in-context at the fixed 3000-token budget, context tokens, retrieval latency (record it), per cause class.
4. Embedding model: local and free (e.g. `all-minilm:22m` via Ollama, or a sentence-transformers model after checking installation); index source chunks only (never hidden tests, never gold), build index at the base commit, fixed seeds, record model version and dimensions.
5. Preregister hypotheses and success thresholds before running (e.g. "H-fusion raises recall@sent on configuration cases by at least 0.15 at no more than +20% tokens"). Only if the offline benchmark shows a real gain is an end-to-end hybrid arm justified, and that needs a new experiment on unseen cases (section 7).
Estimated effort 3 to 5 days, 0 LLM tokens for the offline stage.

## 4. Why not 35/35: what actually fails
The full per-case-run record is in failure-analysis.md; summary of the 44 non-verified case-runs out of 220 (55 per condition):
| Category | Case-runs | Cause |
|---|---|---|
| Expected: non-repairable sites, correct abstention / no patch | 32 | by design (3 insufficient-evidence and 3 runtime-dependency sites) |
| Non-repairable, no diagnosis submitted (`shop_api-030`) | 6 | rationale over 500 characters rejected twice (`string_too_long`), reported as `model_output_malformed` |
| Non-repairable, wrong class (`shop_api-134`, L only: abstained instead of runtime_dependency) | 2 | diagnosis, no effect on repair outcome |
| **Genuine:** `shop_api-020` (L0, G0): right key `shop_api.REDIS_HOST`, right file and line, wrong value `lab_redis` three times, reproducer still fails (`socket.gaierror`) | 2 | patch generation; the F0 loop repeats the identical edit; feedback (L1, G1) fixed it with `localhost` |
| **Genuine:** `shop_api-019` (L0, L1): invalid diagnosis output, rationale over 500 characters twice | 2 | model output vs schema limit; G0/G1 hit it once and recovered |
Not attributable to retrieval, scope policy, the guard or validation: for all 44, no attempt has a policy or validation rejection. Retrieval did not cause any failure, although gold was absent from the sent context in several successful cases (section 3).

**Why diagnosis correctness differs from verified repair.** A diagnosis names the cause class and a target (function or config key). A fix needs the right edit at that target and must pass the reproducer, the visible suite and the hidden suite. `shop_api-020` is the clean example: the diagnosis was exactly right (L0 and G0) and the repair still failed, because the value to write (`localhost`, not the compose service name) was a separate decision the model got wrong without feedback. Conversely, a correct abstention is a success of diagnosis with, by definition, no fix.

## 5. What could raise verified repair, and what that would require
Remaining genuine headroom on this benchmark is small (4 of 180 repairable case-runs), so the improvements below mostly protect against failure modes and widen the harder-case margin; their benefit on the current 35 sites is bounded (at most 1 site per arm at r0).
| Improvement | Addresses | Changes the experiment? |
|---|---|---|
| Tolerant `rationale` handling (truncate server-side or state a lower limit in the schema/prompt; log the rejected text, which is not saved today) | 8 case-runs incl. 2 genuine | **Yes**: edits fingerprinted files, so it defines RC2 |
| Patch loop must not resubmit an identical edit; require a different edit or stop with a reason | `shop_api-020` F0 | Yes (alters F0 behaviour and the loop); RC2 |
| Config-value inference from deterministic evidence (hostname vs compose service vs settings default; extend the existing unresolvable-hostname diagnostic to propose candidate values) | the `localhost` vs `lab_redis` class of faults | Yes (new diagnostics finding, fingerprinted) |
| Reproducible/queryable feedback quality: richer visible-test output (full assertion, variable values, stderr trace) | patch attempts 2 and 3 | Yes, as feedback variant F2; keep visible-only |
| Retrieval: hybrid BM25 + graph + embeddings, rerank, per-class budgets | recall/precision/rank, config cases (recall 0.33) | Offline benchmark: no. End-to-end arm: yes |
| Structured/scoped patch output (already used) and dependency-aware analysis (call-graph impact of the edit) | regressions (0 so far) | Marginal here; needs a harder benchmark |
| Abstention: confidence from evidence sufficiency, calibrated on dev | `shop_api-134` L | Yes |
| Offline analysis tooling, retrieval-latency logging outside the fingerprinted path, test fixes, docs, UI | observability | **No** |

**What can be done without touching the experiment:** analysis scripts and reports, the offline retrieval benchmark on the dev split, the dev-split hybrid prototype in new modules (new files outside the 28 fingerprinted ones, not wired into any frozen condition), documentation, tests, frontend/back-end work. **What needs a new experiment:** every change to a fingerprinted module (prompting, diagnose, tools, patch loop, pipeline, retrieval, repair, diagnostics), because it changes RC1 (fingerprint `ee3d8d87…`).

## 6. What the 35-case results show, and do not
**They show:** on these 35 sites (one case per variant group, drawn blind) RC1 diagnosed the cause class correctly in 32/35 (L0) and 35/35 (G0) and verified a fix in 27 (L0), 28 (G0), 28 (L1) and 29 (G1) of 35 case-runs at replicate 0; on the 29 repairable sites that is 93% to 100%; zero visible-suite regressions; zero provider failures; zero unsupported claims; every failure traces to a model-output schema limit or a repeated wrong value, not to a retrieval, policy or validation weakness.
**They do not show:**
- *Generalization to the split or to other systems:* 35 of 151 cases from one service (`shop_api`), selection-based sampling does not weigh variant groups by size.
- *Graph superiority:* the arms differ in 1 case-run of 35 for fixed (G only 1, L only 0) and 3 for diagnosis class; the same cases flip between replicates for the same arm, so the differences are inside replicate noise. Context tokens favour G (about 1,712 vs 2,336) and rank quality is better, but that is retrieval, not repair.
- *Feedback effect:* one case (`shop_api-020`, 2 arms, not independent) where F1 succeeded after F0 failed, none where F1 hurt. That is 1 of 45 repairable case-runs per arm; no effect size can be stated from it.
- *Confidence intervals (Wilson 95%, replicate 0):* G0 fixed 28/35 = 80% (64% to 90%); fixed on repairable sites 28/29 = 97% (83% to 99%). Intervals for L0 and G0 overlap almost entirely. Replicates are not independent samples of sites, so pooled counts across replicates are descriptive only.
- *Comparison with v4/v3:* different pipeline, prompts, evidence and cases; qualitative only.
- A correction recorded here: the stage-2 write-up described the runtime-dependency failures as "the model returned no tool call"; the saved traces show the specific cause: a `string_too_long` schema rejection of the 500-character rationale.

## 7. Prioritized plan
**A. Immediately, without affecting frozen research (no tokens)**
1. Keep RC1 and all results as they are (done). Archive this analysis.
2. Make test isolation permanent (done today: the real `runs/axforge_keys_verified.json` no longer changes unit-test pacing; fix in `tests/conftest.py`).
3. Offline retrieval benchmark on the dev split with the existing L and G arms (baseline numbers, retrieval latency recorded), 1 to 1.5 days, 0 tokens.
4. Build the hybrid retrieval prototype and embedding index in new modules, evaluate offline vs the baseline, 2 to 3 days, 0 tokens; check Ollama/sentence-transformers availability first.
5. Save rejected-submission text (audit) and per-arm retrieval latency in a non-frozen logging path (new logging only; verify it is not in the fingerprint list).

**B. Requiring a separate experimental condition (new RC2; all frozen artifacts preserved)**
1. RC2 = RC1 + rationale-cap fix + no-identical-retry rule + config-value diagnostic. Expected benefit: removes the only observed genuine failure modes (up to 4 case-runs at r0 in these data, 0 to 2 sites). Risk: the changes were motivated by test-split failures, so **the test split cannot be used as clean confirmation**; validate RC2 on the dev split and on a fresh blind draw from sites untouched by the analysis, label cases already analysed as exploratory. The remaining RC1 allowance (about 743k combined tokens) would cover roughly a full replicate of 12 cases (about 600k) or a regression check on dev; it does not cover a replicate of all 35 sites in four conditions (about 1.8M). Dev effort 1 to 2 days plus a verification run of roughly 300k to 600k tokens.
2. Complete the RC1 replicates for the stage-2 sites (r1, r2): about 1.1M tokens each (not affordable under the 4.8M internal ceiling; a seeded subset of about 8 sites per replicate costs about 400k).
3. Hybrid end-to-end arm H (only if the offline benchmark justifies it): new condition H0/H1, new run directory, 12 to 24 sites, about 600k to 1.2M tokens.
4. Feedback variant F2 (richer visible output): needs cases where F0 fails; with a 97.8% repair rate such cases are rare, so it needs a harder or larger case set rather than more replicates of these 35.

**C. Trade-offs.** The biggest scientific limit is not the pipeline but the benchmark: it is nearly saturated (all code faults fixed), so it cannot discriminate between retrieval or feedback variants. The most valuable investment is therefore a harder, larger set of cases (more services, multi-file faults) before spending tokens on more RC1 replicates.

## Appendix A: coverage matrix
Cells are L0 G0 L1 G1 (X = record present, - = missing). Source data: `results/analysis/coverage_matrix.csv`.

| case | stage | cause class | r0 | r1 | r2 |
|---|---|---|---|---|---|
| shop_api-008 | 1 | application_code | XXXX | XXXX | XXXX |
| shop_api-019 | 1 | configuration | XXXX | XXXX | XXXX |
| shop_api-030 | 1 | runtime_dependency | XXXX | XXXX | XXXX |
| shop_api-047 | 1 | application_code | XXXX | XXXX | ---- |
| shop_api-066 | 1 | application_code | XXXX | XXXX | XXXX |
| shop_api-073 | 1 | application_code | XXXX | XXXX | XXXX |
| shop_api-092 | 1 | application_code | XXXX | XXXX | XXXX |
| shop_api-100 | 1 | application_code | XXXX | XXXX | ---- |
| shop_api-102 | 1 | insufficient_evidence | XXXX | XXXX | XXXX |
| shop_api-119 | 1 | configuration | XXXX | XXXX | XXXX |
| shop_api-148 | 1 | configuration | XXXX | XXXX | ---- |
| shop_api-181 | 1 | configuration | XXXX | XXXX | ---- |
| shop_api-013 | 2 | configuration | XXXX | ---- | ---- |
| shop_api-020 | 2 | configuration | XXXX | ---- | ---- |
| shop_api-026 | 2 | runtime_dependency | XXXX | ---- | ---- |
| shop_api-028 | 2 | insufficient_evidence | XXXX | ---- | ---- |
| shop_api-035 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-045 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-046 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-057 | 2 | configuration | XXXX | ---- | ---- |
| shop_api-060 | 2 | insufficient_evidence | XXXX | ---- | ---- |
| shop_api-075 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-077 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-088 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-091 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-103 | 2 | configuration | XXXX | ---- | ---- |
| shop_api-105 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-115 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-128 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-134 | 2 | runtime_dependency | XXXX | ---- | ---- |
| shop_api-147 | 2 | configuration | XXXX | ---- | ---- |
| shop_api-150 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-163 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-169 | 2 | application_code | XXXX | ---- | ---- |
| shop_api-172 | 2 | application_code | XXXX | ---- | ---- |
