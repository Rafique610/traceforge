# Why TraceForge diagnoses wrongly: root-cause report (investigation only, 24 Nov 2026)

No code, prompt, setting or result was changed. No model request was made (ledger unchanged: 872,241 committed). Everything below comes from saved artifacts
(`results/*`, `runs/evidence`, the on-disk LLM cache, which stores the exact request and reply of every call) and local read-only code analysis.
Ground truth (gold symbols, mutation patches, reproducers) was used only offline, never in a prompt. patch_v3 and patch_v4 runs are cited by run id; the diagnose
prompt and its inputs are identical in both, so diagnosis findings apply to both, but they are not pooled into one statistic.
Labels: CONFIRMED (shown by code or artifacts), LIKELY (strongly supported, not demonstrated), UNKNOWN.

## 1. Headline
**The earliest divergence is layer A/C (evidence collection plus what the prompt contains): for faults that do not show in the running lab, nothing fault-specific
ever enters the model's input.** The incident symptom is not in the prompt, the retrieval query is the service name, and the 33 evidence items for four different code
faults are the same text. The model then latches onto the one anomaly present in every case. This is mostly an information problem, not a reasoning problem. There is
also a reasoning failure on top, and two harness defects that distort outcomes.

## 2. Trace of shop_api-010 (code fault: `discount_pct` lost `min(pct, cap)`)
| Step | What happened | Label |
|---|---|---|
| 1 Failure | A quote with coupon `staff50` returns 9.35 instead of 11.10 (the 30% cap is not applied). It is visible only by calling `/orders/{id}/quote?coupon=staff50`; the HTTP status is 200. | CONFIRMED (reproducer output in the F1 feedback) |
| 2 Evidence | 33 items: 5 health (all healthy, `/health` ok), 1 startup log, 7 compose env lines, 15 static settings declarations, 4 compose services. The collector posts one plain order, so the failing path is never exercised. No item mentions pricing behaviour. | CONFIRMED (`lab_collect.py` `_post_order`; evidence file) |
| 3 Lexical retrieval | Query terms are `['shop','api','shop_api']` (service name only; `build_query` takes signal lines from log/health and none match). Top hits: `test_settings.py`, `compose.yaml`, `.env.example`, settings fields. | CONFIRMED |
| 4 Graph retrieval | Identical to lexical (35 hits, same order). The anchor list is empty, so every graph term (proximity, expansion, test_link) is 0. | CONFIRMED |
| 5 Files selected | None of them is `app/coupons.py`. | CONFIRMED |
| 6 Prompt | 13,237 chars: service name, evidence, those settings/compose chunks. `diagnose_v1.md` has no symptom field. | CONFIRMED |
| 7 Model | Opening text: "investigate the apparent contradiction between the container environment (DB_HOST=lab_db...) and the settings dump showing localhost defaults". It reads EV-0014 and EV-0005, calls `get_neighbors` (empty), then two `read_symbol` calls on invented paths (`app/main.py::health`, `app/health.py::health`, both "symbol not found"). It submits `configuration shop_api.DB_HOST` and lists EV-0005 (health ok) as *contradicting*. | CONFIRMED (cache) |
| 8 Why | It was asked to find the root cause of an incident it was never told about; the only anomaly in the text is declared default `'localhost'` next to compose `DB_HOST=lab_db`. | CONFIRMED (its own rationale) |
| 9 To patch | `cause_class`, `config_key` and `rationale` go straight into patch_v4; `_verbatim` shows `settings.py`. All 3 L0 patches (v4cap8k run) edit `Settings` env handling. The patch stage faithfully executes the wrong diagnosis. | CONFIRMED |
| 10 First divergence | Steps 2 and 6: no fault signal and no symptom reach the model. | CONFIRMED |

## 3. Case-by-case (L0, AxForge; v3 = pilot8, v4 = scr/scrB)
| Case (gold) | Fault signal in evidence? | Gold file in prompt (L = G)? | Model output | Failing layer | Recoverable from evidence alone? |
|---|---|---|---|---|---|
| 010 code missing_cap | No (32/33 items same as 006/018/022) | No | config DB_HOST | A, then B/C | No |
| 006 code wrong_argument | No | No | config DB_HOST (same rationale) | A | No |
| 018 code wrong_argument | No | No | config db_host (same) | A | No |
| 022 code missing_cap | No | No | final submit config DB_HOST, **discarded**: rationale over 600 chars, `budget_exhausted` | A, then harness (E) | No |
| 049, 054 worker code | No (worker healthy, log fine) | No | insufficient_evidence (honest: "no failure observable") | A | No |
| 008 worker code wrong_formula | No | No | insufficient_evidence | A | No |
| 005 config tax_rate 1.17 | **Yes**, one changed settings line | settings in prompt | insufficient_evidence after 4 calls, 2 invalid | D (missed a present clue; distractor) | LIKELY yes (a rate above 1) |
| 012 config shipping_fee 0.00 | Yes, one changed line | in prompt | insufficient_evidence after 2 calls | D or ambiguous | UNKNOWN (0.00 could be intended) |
| 015 config shipping_fee 499 | **Yes** | in prompt | final submit `insufficient_evidence` **discarded** (rationale 1,043 chars), `budget_exhausted` | D + harness | LIKELY yes (4.99 vs 499 next to free_shipping_over 50) |
| 016 config tax_rate 0.18 | Yes, but 0.18 is plausible | in prompt | final submit insufficient discarded (808 chars), 2 failed submits | harness; weak evidence | No (needs a reference value) |
| 021 worker config order_queue default `order:confirm` | Yes (default typo), but the runtime log shows `orders:confirm` (compose env overrides it) | in prompt | insufficient_evidence; it noticed the typo and rejected it because the runtime log contradicts it | A: fault latent in the deployed env | No without symptom (the abstention is defensible) |
| 023 worker config max_retries | Weak | in prompt | insufficient_evidence | A | UNKNOWN |
| 013 config redis_port 7379 | **Yes** | in prompt | class `application_code` at `settings.py::Settings.redis_port` (location correct, class differs from gold) | D (class), then E (over-edit) | Yes (location achieved) |
| Redis family 001, 020, 040, 139 (wrong_host) | **Yes**: traceback in logs (`gaierror`, frames) | G puts the gold file in the prompt for 020 and 040 only; L misses it | correct class and target in all runs | none | Yes |
| 007 dependency_stopped | Yes (health) | n/a | correct runtime_dependency | none | Yes |

Summary, 16 distinct traceless non-Redis cases at L0 (pilot8 + list A): 11 abstained (3 recorded as `budget_exhausted`, see E), 4 wrong, 1 right. All cases with a log traceback or a dead dependency were correct.

## 4. Layer-by-layer findings
### A. Evidence collection
- **CONFIRMED** For the code-fault cases 010, 006, 018, 022 the evidence bundles are identical except the startup-log item (32 of 33 items equal after normalising ids and timestamps). Config-fault cases differ from 010 in exactly one item (the corrupted settings default). No evidence item distinguishes one code fault from another.
- **CONFIRMED** The lab is healthy for these faults: `/health` ok, logs show 200/201 traffic (the model says so in 015, 016, 021, 023, 054). The collector sends one order without a coupon, so pricing faults never surface. The failure exists only in the reproducer test.
- **CONFIRMED** Every shop_api bundle contains the same distractor: static declared defaults (`db_host='localhost'`, `redis_host='localhost'`) beside compose env (`DB_HOST=lab_db`). It is a benign property of the lab (env overrides defaults) but looks like a contradiction.
- **CONFIRMED** The "settings dump" items (kind `config`, path `settings.py`, line N) come from `declared_settings(src)`, a static parse of class declarations (`evidence/collector.py:131-134`), not from the running process. The same `config` kind is used for the effective env (`DB_HOST=lab_db`).

### B. Retrieval (graph and lexical)
- **CONFIRMED** The query for traceless cases is the service name: terms `['shop','api','shop_api']` (shop_api cases) or `['worker']` (worker cases). BM25 ranks chunks by that, which returns settings and compose.
- **CONFIRMED** Graph construction is real: 27 config_key, 80 function, 19 method, 24 class, 52 test, 28 settings_field and 4 service nodes; 18 edge types including calls (110), reads_config (102), tests_covers (71), service_env (21), depends_on (5). There are **no route/endpoint nodes**, so an HTTP request cannot be linked to its handler.
- **CONFIRMED** Why G equals L: graph terms need anchors, and anchors come only from trace frames or config keys named inside log/health text (`retrieval/anchors.py` `build_query`). Anchors were empty in 15 of 15 inspected traceless cases (L = G in all 15) and present in 5 of 5 cases with a log traceback or a dead dependency (L differs from G in all 5: 001, 020, 040, 139, 007). `graph_scores` with no anchors returns `{}` and the G weights add 0.
- **CONFIRMED** Where G is active it changes the context: the gold file is in the prompt under G but not L for 020 and 040. Outcomes did not change because those diagnoses were already correct from the logs. Graph retrieval therefore has **no measured outcome benefit** in any run so far.
- **LIKELY (offline, no model)** The gold symbol is not lexically retrievable even from the symptom (not in the BM25 top 50 for 010, 006, 018, 022), but it lies 1 hop (tests_covers or calls) from the top-10 symptom-ranked chunks in 6 of 7 traceless code cases. The graph could therefore help if anchored on symptom-matched tests. UNKNOWN until tested.

### C. Context construction
- **CONFIRMED** `render_evidence` prints `[id kind service] content` and drops `path` and `line`. The model cannot see that EV-0014 is a static declaration at `settings.py:14`. In 006, 010, 018 and 022 its rationale calls it "the runtime settings dump" and concludes the env vars "are not applied".
- **CONFIRMED** The diagnose prompt has no symptom: `diagnose_v1.md` has only `{service}`, `{evidence}` and `{context}`. `real_run.py` computes `symptom_for` but uses it only for a hash.
- **CONFIRMED** Tools are not discoverable: there is no file list or search, so the model guesses paths (`read_symbol` "symbol not found" in 006 x2, 010 x2, 013 x2, 018, 015, 016, 022 x2). `get_neighbors` on a class returned `[]` in 010.
- No evidence of truncation of the relevant items in these cases (context 12k chars; the relevant settings lines are present).

### D. Diagnosis reasoning
- **CONFIRMED** Four different code faults get the same wrong diagnosis with near-identical rationale (006, 010, 018, 022): the output is a function of the constant evidence, not of the fault.
- **CONFIRMED** Self-inconsistency: the model cites `/health` (db ok, redis ok) as *contradicting*, then diagnoses that the service connects to localhost. If it did, the db and redis checks would fail. The schema has `contradicting_evidence_ids` but nothing forces a reconciliation.
- **CONFIRMED** It treats a static declared default as a runtime value (see C).
- **CONFIRMED** 005 (tax_rate 1.17) and 015 (shipping_fee 499) contain the fault as one changed line; the model abstained in both. LIKELY attention capture by the constant distractor; UNKNOWN whether a cleaner prompt fixes it.
- **CONFIRMED** The same evidence pattern yields different decisions across cases (abstain in 015, 016, 021, 023, 049, 054; commit to DB_HOST in 006, 010, 018, 022): the decision at the margin is unstable.
- Defensible behaviour: abstaining in 021, 049 and 054 ("no failure observable") is a correct reading of the evidence it had and is not a reasoning error.

### E. Diagnosis-to-patch interface and harness
- **CONFIRMED (harness defect)** All three `budget_exhausted` cases (015, 016, 022) ended because the model's last `submit_diagnosis` had a `rationale` over the 600-character schema cap (`string_too_long`; re-validated offline on the cached final replies: 1,043 / 808 / 866 chars). A rejected call consumes a tool call, so the budget ran out. 016 failed twice. Offline effect: the discarded submissions were insufficient_evidence (015, 016) and a wrong DB_HOST (022), so accuracy would not have changed, but the outcome label is wrong and tool calls are wasted.
- **CONFIRMED** The patch stage follows the diagnosis exactly (010: three patches on `Settings`). It adds no file-selection error.
- **CONFIRMED (over-edit)** 013 (v4): the diagnosis names host and port. The patch changes `redis_port` 7379 to 6379 (correct) and also `redis_host` "localhost" to "lab_redis" (not in the gold fix), and the hidden suite failed. Under v3 the same case was TEST_VERIFIED. UNKNOWN whether the cause is the v4 prompt or sampling.
- **LIKELY** The class label for 013 (`application_code` vs gold `configuration`) reflects an undefined boundary in `diagnose_v1.md`: a wrong default declared in Python settings is both.

## 5. Model and inference configuration
- **CONFIRMED** AxForge `glm-5.3-flash`, temperature 0, `seed` in the cache key but removed from the provider call (`gateway.py` pops it), `reasoning_effort` unset (provider default), diagnose `max_tokens` 4096, tool budget 6, `MAX_PROVIDER_FAILURES` 2, one request at a time.
- **CONFIRMED** Temperature 0 is not deterministic here: 010 L0 attempts 1 to 3 sent the same prompt hash (`d70057..`) and returned three different patches (diff sha `3b8096..`, `f9ecbd..`, `6b7838..`) with 7,688 / 2,290 / 1,254 output tokens.
- **CONFIRMED** The conditions differ only in retrieval mode and (patch stage) feedback. For 010 the L0 and G0 diagnose requests have identical message hashes, so G0 was a cache replay.
- **CONFIRMED** Hidden reasoning can consume the whole output cap (diagnose: 11 of 63 distinct requests at 2,000 tokens or more, max 4,096). It did not cause a wrong diagnosis in the inspected cases; it explains stalls and cost.
- **UNKNOWN** The provider's effective reasoning effort, and whether diagnose outputs vary run to run (no replicate has been run).
- Caching is not a cause of wrong diagnoses; it explains replays (G0, L1/G1 attempt 1).

## 6. Direct answers
1. Earliest failure point: layer A/C. The model's input contains no fault-specific information and no symptom (CONFIRMED).
2. Primary root cause: evidence collected from a healthy lab plus a prompt without the symptom (CONFIRMED for the 7 traceless code cases; for config cases the fault is a single line among 15 and the model sometimes misses it).
3. Secondary causes: a constant distractor with ambiguous labelling (path and line dropped, static vs effective values), service-name-only retrieval, no route nodes, undiscoverable tools, submit validation burning the budget, and nondeterministic patch sampling.
4. Graph retrieval genuinely helping: not shown. It is structurally sound but inactive in 15 of 20 inspected cases, and it made no outcome difference in the 5 where it was active.
5. Sufficient evidence: no for the 7 traceless code cases; partly for traceless config cases; yes for trace and dependency cases.
6. Reasoning wrong despite sufficient evidence: yes in 005 and 015 (LIKELY), and the self-contradicting DB_HOST diagnosis (CONFIRMED), where the evidence was not sufficient.
7. Interface adds errors: yes, but not file selection. The 600-char cap and budget interaction (CONFIRMED) and the 013 over-edit (CONFIRMED).

## 7. Recommended permanent changes, ranked by expected impact
1. **Put the reporter's symptom (already leakage-scanned) and the visible reproducer failure text into the diagnose prompt.** This removes the primary cause. Correction to the earlier v5 plan: for value faults the reproducer traceback contains only the test frame (`/reproducer/test_symptom.py:7`), not an app frame, so "reproducer frames to source" will not localise them. Localisation must come from symptom-derived retrieval (item 3). Independent test: paired diagnose-only L0 runs on a fixed case set, with and without the symptom, same evidence.
2. **Make evidence honest and distinguishable:** render path:line and label static declarations "declared default (source), not runtime value". Independent test: offline prompt diff, then a small paired run on the four DB_HOST-fixated cases (006, 010, 018, 022).
3. **Symptom-derived retrieval query plus graph anchors from matched tests** (and route nodes). Independent test at zero model cost: for all 151 cases compute gold-in-context at the same budget for L vs G with the new query.
4. **Fix submit handling:** validation errors do not consume the tool budget; trim or soft-limit `rationale`. Independent test: replay the three cached final submissions (zero cost) and unit tests.
5. **Tool discoverability:** a file/symbol listing or search tool. Test: `read_symbol` error rate on replays.
6. **Define class boundaries and require reconciling contradicting evidence** (diagnosis claim validation). Test on 013 and the 006/010/018 set.
7. **Patch over-edit guard** (change only the diagnosed key). Test: policy unit tests plus 013.

Items 1, 2 and 6 change model input and must be versioned (pipeline v5) and run as ablations so the graph and feedback conditions stay separable.

## 8. What is still unknown, and the smallest controlled investigation
- Whether adding the symptom moves the model off DB_HOST to the right target needs model calls. Smallest test: diagnose-only, L0, cases 010, 006, 018, 005, with only the diagnose input changed, paired against the existing no-symptom runs (same cases, same evidence). About 4 x 30k = 120k AxForge tokens. Not run; it needs your approval and a healthy provider.
- Diagnose-stage determinism: send the same diagnose request twice for one case (about 30k tokens).
- Whether `reasoning_effort` changes the DB_HOST fixation: one case, two effort levels.

Scripts used (outside the repo, in the session scratchpad): `trace010.py` (cache replay), `layers.py`, `hops.py`, `dxprompt.py`.
