# Pipeline v5: architecture investigation and implementation plan (PROPOSAL, not implemented)

Status: proposal awaiting approval (24 Nov 2026). Nothing here is implemented. Each statement is tagged
**[CONFIRMED]** (read in code or measured in saved artifacts, no new model call) or **[HYPOTHESIS]** (needs a test).
No model request was made for this investigation. Descriptive counts below are not pooled across patch_v3 / patch_v4.

## 1. Current architecture map

```
collect evidence (lab_collect: health, logs, config dump, settings, compose)   -> EvidenceBundle (EV-xxxx items)
 -> retrieve (L: BM25+anchors | G: +graph proximity/test-link)                  -> ContextBundle (<=12k chars)
 -> diagnose (diagnose_v1; tools read_evidence/read_symbol/get_neighbors/submit_diagnosis, budget 6)
 -> ToolContext/SubmitDiagnosis -> patch (patch_v4; SEARCH/REPLACE text) -> policy -> sandbox
 -> repair loop (3 attempts; F1 feeds previous visible output) -> hidden suite once
```
Files: `agent/diagnose.py`, `agent/tools.py`, `agent/prompts/diagnose_v1.md`, `agent/prompting.py`, `retrieval/{anchors,retrieve,lexical}.py`,
`agent/patch.py`, `agent/prompts/patch_v4.md`, `repair/{edits,policy,loop}.py`, `agent/repair_run.py`, `evaluation/real_run.py`, `agent/real_sources.py` (HiddenLeakGuard).

## 2. Root causes

### A. Diagnosis
1. **[CONFIRMED] The symptom never reaches the diagnose prompt.** `symptoms.symptom_for` is computed in `real_run.py` (and `e2e.py` for the incident record) but the
   diagnose template has only `{service} {evidence} {context}` (`diagnose_v1.md`); `real_run` uses the symptom only for `symptom_sha256`. For a behavioural fault the
   model is therefore never told what is wrong ("quote total is wrong"). Checked by rendering the prompt without a model (`dxprompt.py`): no symptom field.
2. **[CONFIRMED] For cases with no trace frame the evidence is generic and the retrieval query is generic.** Evidence for shop_api-010 is health OK, startup log, 7 compose env
   lines, 15 settings defaults, 4 compose services: no failing request, no failing test output. `build_query` builds BM25 terms from `service + log/signal lines + names` of
   that evidence; the top hits for 010, 013 and 006 are the same (`test_settings.py`, `compose.yaml`, `.env.example`). The gold file (`app/coupons.py`) is **not** in the
   prompt for 010 or 006 (L or G), only for 013.
3. **[CONFIRMED] The model was misled by a benign artefact.** For 010 it diagnosed `shop_api.DB_HOST`: settings default `db_host='localhost'` (EV-0014) next to compose
   `DB_HOST=lab_db`, while `/health` shows db ok. The default-vs-env display is normal, and nothing in the evidence contradicts it except the (omitted) symptom.
   Two of six tool calls were `read_symbol` failures (`ok:false`), i.e. 1/3 of the budget wasted.
4. **[CONFIRMED] Tool budget and abstention.** Of 16 distinct non-trace-frame cases run at L0 on AxForge (descriptive, patch versions not pooled; diagnose prompt
   identical across them): 11 abstained (of which at least 3 were `budget_exhausted`; the 4 pilot8 abstentions were not split by reason here; 0 correct targets), 4 wrong class, 1 correct class and target. Every Redis-family case
   (traceback frames present in evidence; 4 distinct cases, 6 runs) had correct class and target. **[HYPOTHESIS]** the presence of a stack frame is what makes diagnosis
   workable; n is small and correlation is not proof.
5. **[CONFIRMED] Dataset shape limits purely deterministic diagnosis.** Of 151 test cases, behavioural application_code families (boundary, rounding, wrong_formula, case_handling,
   missing_cap, ...) are 47 shop_api + 20 worker (67 in total); they raise no error. Deterministic detection can cover roughly: dependency_stopped 12, intermittent_no_logs 12 (deterministic
   abstain), wrong_host/wrong_port 6, plus startup validation errors (malformed_value, invalid_date, 16, **[HYPOTHESIS]** only if the validation error is in the logs).
   That is about 30%, not the majority. The rest needs a test-failure signal (see 3.A).
6. **[CONFIRMED] Unused deterministic signal.** The repair loop runs the visible reproducer on the base commit before any patch (`repair/loop.py` baseline). Its pytest output
   contains the failing assertion and project frames (e.g. `app/queue.py:39: in enqueue_confirmation` seen in saved F1 feedback). It is never used for diagnosis, retrieval or
   anchors. It is a visible-test execution artifact, so using it is compatible with the no-hidden-information rule.
7. **[CONFIRMED] No claim validation.** `dispatch(submit_diagnosis)` checks only that cited evidence ids exist and that a path is under the service. It does not check that
   a cited item supports the claim, that `config_key` exists in settings, or that `qualname` exists in the file.

### B. Patch truncation
1. **[CONFIRMED] Truncation is a reasoning overrun, not a long patch.** Across all saved artifacts: 70 distinct patch requests; 67 produced 55-300 output tokens, one 1655, three
   hit the 4096 cap with empty content (`finish_reason=length`, 018/006/010-attempt-2). A compact edit is ~100 tokens; the failure mode is hidden reasoning consuming the cap.
   Diagnose shows the same tail: 63 distinct requests, median 662, 11 >= 2000, max 4096.
2. **[CONFIRMED] The prompt asks for "SEARCH/REPLACE blocks and nothing else"** in free text; reasoning and payload share one completion budget. The 8192 cap applied in
   the previous task (`PATCH_MAX_OUTPUT_TOKENS`) is a stopgap and not a design: its effect is being validated in `official-axforge-*-v4cap8k-test` (in progress when this was written).
3. **[CONFIRMED] Application is already deterministic and strict** (`repair/edits.py`: exact single match, `no_match`, `ambiguous_match`, `file_missing`, allowlist, policy, worktree apply).
   The weak point is the text format: a regex over free text (`_BLOCK`) that drops whole replies on any formatting slip, and edits are applied to a dict in memory before the worktree
   (partial application cannot reach disk, but multi-block failure reporting is first-error-only).
4. **[HYPOTHESIS]** a `submit_patch` tool call (JSON arguments) or `response_format` schema keeps the payload separate from reasoning and shortens it. Whether AxForge enforces schemas
   or reasoning still consumes `max_tokens` with tool calls is **unverified**; the provider's real maximum output limit is not documented (no AxForge limit in the repo docs; the
   only measured evidence is 4096 reached and 8192 pending).

### C. Feedback guard
1. **[CONFIRMED]** `HiddenLeakGuard` builds a blacklist of every hidden test function name, hidden file name (except conftest.py) and the marker `hidden_tests`, and asserts none is a
   substring of `json.dumps(messages)`. Reproducer and hidden suites share names by design (`test_price_1`, `test_price_2` in 010), so F1 feedback (the reproducer output) is blocked.
2. **[CONFIRMED]** The guard checks names only. Despite its docstring ("names/paths/lines") it does not check hidden assertion text or expected literals.
3. **[CONFIRMED]** `TestRunResult` has no `suite` field and `_feedback()` builds a bare string, so feedback carries no provenance; nothing in the type system stops a hidden
   result from being passed as feedback (only call-site discipline).
4. Interim state (previous approved task, not part of v5): the guard accepts an optional `visible_dirs` and exempts names defined in the case's own visible test files.
   Name-provenance by directory scan is weaker than the design below and would be superseded.

## 3. Proposed permanent architecture

### 3.A Hybrid diagnosis (pipeline_v5)
Stages, each with a typed output and a recorded artifact:
1. **Evidence collection (unchanged) plus a new visible-failure artifact.** Before diagnosis, run the case's visible reproducer on the base commit (already done in the loop; hoist it)
   and store it as an evidence item `kind="visible_failure"` with provenance `visible_reproducer`. Pass through the existing leakage scanner (`faultgen.leakage.scan_visible`) so gold terms
   cannot appear. **Decision D1 below.**
2. **Deterministic diagnostics (`diagnostics/` package, pure functions over EvidenceBundle, no model, no case ids):** each rule returns `Finding(kind, evidence_ids, target?, confidence, rule_id)`.
   Candidate rules, all dataset-agnostic: (a) dependency not running/unhealthy (health items); (b) env/settings mismatch: a value that the service logs as failing vs the compose/env value;
   (c) hostname resolution errors (`gaierror`, `Name or service not known`) cross-referenced with compose service names; (d) startup validation errors naming a settings key;
   (e) `ModuleNotFoundError/ImportError/SyntaxError/TypeError` with file:line; (f) traceback or pytest frames mapped to `(path, qualname)` through the code graph (this generalises the existing
   anchor mechanism to the reproducer output); (g) no logs + intermittent => explicit abstention finding. Findings are *hints with evidence ids*, not verdicts, except where a rule is
   defined as decisive (dependency down).
3. **Source localisation (retrieval):** feed (f) as forced trace anchors so the existing L/G machinery operates on every case. **This changes the L vs G contrast: today the arms are
   identical when no frames exist (9 of 12 earlier cases). With reproducer frames G can differ from L on most cases. That is intended, but is a research-visible change: see D2.**
   Also guarantee the diagnosed file's text is shown (as `<source_file>` blocks already do for the patch stage).
4. **Structured AI diagnosis:** add `{symptom}` and the deterministic findings to the diagnose prompt (symptom text is already leakage-scanned). Replace free `rationale` with a
   `claims: [{claim, evidence_ids[], kind}]` array. `submit_diagnosis` keeps its current fields so old artifacts remain readable.
5. **Claim validation (code):** reject (as a tool error that does not consume a tool call, or consumes at most one) a diagnosis when: `config_key` is not a known settings key of the service;
   `path::qualname` does not exist in the graph; a cited evidence id does not mention the target/class (token overlap or rule-based support check); the target contradicts a decisive
   deterministic finding. Rejected diagnoses are recorded with the reason.
6. **Abstention rules:** abstain (typed reason `insufficient|contradictory|budget`) only when no evidence supports a target or two decisive findings conflict; budget exhaustion becomes a forced
   `submit_diagnosis` request (tool choice) instead of a silent abstain. Hypothesis: this alone converts some of the budget_exhausted cases. Requires care: it changes the
   abstention semantic used in results.

Why it does not depend on hidden tests: every input is evidence collected from the running lab, the base source tree, or the *visible* reproducer run; hidden results are evaluation-only and never constructed.

Expected accuracy gain: **unmeasured** (hypothesis: material for behavioural cases because the symptom and failing assertion/frames are the missing inputs; not claimed).

### 3.B Structured patch
- New tool `submit_patch` (OpenAI-format function call) with schema:
  `{"edits":[{"path":str,"op":"replace","old":str,"new":str,"context_before"?:str,"context_after"?:str,"expected_matches":1}]}`, `maxItems 3`, `old/new` max 1500 chars; reasoning is
  never in this payload. Fallback: the existing SEARCH/REPLACE parser remains for old artifacts and as the pure-text path.
- Deterministic pipeline, in order: schema validation -> allowed-file check -> read base text -> exact match count == expected (0 => `no_match`, >1 => disambiguate with
  context_before/after, else `ambiguous_match`) -> build all new texts in memory, atomic (all or none) -> `ast.parse`/`tomllib`/yaml syntax check per file -> policy -> worktree apply -> reproducer + visible.
- Truncation: a reply with `finish_reason=length` and no payload is recorded `NO_PATCH/output_truncated` and **not cached** (done in the previous task). Retry policy (decision D3): one
  retry at the same attempt index with the same cap is a different request and costs tokens, so it should be explicit and counted as part of the attempt, never as a replicate.
- Output budget: measure, then set. Proposed: patch cap stays 8192 only if the pending validation shows no truncation; a second lever is `reasoning_effort` (already a gateway setting, default None)
  set to "low" for the patch stage. Both are *configuration* changes to be listed in pipeline_v5. We will not claim a safe cap without a bounded probe (about 6 requests, ~40k tokens max).

### 3.C Provenance-based feedback
- Introduce `FeedbackItem{source: "visible_reproducer"|"visible_suite", run_id, suite, test_ids[], text, sha256}` created only by `_feedback()` from a `TestRunResult` returned for a request whose
  `suite in {reproducer, visible}`; add `suite` to `TestRunResult` (or wrap it in a `SuiteRun` dataclass) so a hidden result is structurally unable to become feedback (constructor rejects `suite=="hidden"`).
- Guard v2 (on the serialized final messages, which is what the provider receives):
  1. blocked: hidden-only test names, hidden file names, `hidden_tests` and hidden paths (as today);
  2. blocked: hidden assertion fragments (normalised hidden `assert` statements and literals that occur in no visible file) **[HYPOTHESIS: needs a false-positive check on the 151 cases]**;
  3. a name that is **both** hidden and visible is allowed only when it occurs inside a `FeedbackItem` span (or the visible-test context) whose provenance is verified and whose
     visible definition is verified by AST in the visible files; the same name outside such a span still fails closed;
  4. each prompt records `feedback_item_ids` + sha256 and the exact text delivered (already in `requests.jsonl`; extended with provenance).
- Security argument: a test *name* shared with a visible test reveals nothing hidden (it is already visible); the hidden body, hidden-only names, files and paths remain blocked as a
  set difference computed per case; and the only way for result text to enter a prompt is through a typed item whose origin is a visible run. The guard remains a defence in depth, not the only barrier.

## 4. Files that would change
`agent/prompts/diagnose_v2.md`, `patch_v5.md` (new); `agent/diagnose.py`, `agent/tools.py` (submit_patch, claims, claim validation), `agent/patch.py`, `agent/prompting.py` (VERSIONS, symptom render),
`agent/pipeline.py` (symptom + findings plumbing), `diagnostics/` (new package + tests), `retrieval/anchors.py` (reproducer frames), `repair/{edits,loop}.py` (structured edits, FeedbackItem), `contracts/test_run.py` (suite),
`agent/real_sources.py` (guard v2), `evaluation/real_run.py` (artifacts: findings.json, feedback items, pipeline version), `agent/gateway.py` (per-stage cap, optional reasoning effort in cache key),
`config.py` (pipeline_version), docs.

## 5. Schemas and validation boundaries
`Finding`, `Claim`, `SubmitDiagnosis v2` (additive fields), `SubmitPatch`, `FeedbackItem`, `PipelineConfig{pipeline_version, diagnose_prompt, patch_prompt, patch_max_tokens, reasoning_effort, visible_failure_in_evidence}`.
Boundaries: (1) provider -> schema; (2) schema -> deterministic validators; (3) validators -> worktree; (4) visible run -> `FeedbackItem` -> prompt; (5) final serialized prompt -> guard v2 -> provider.

## 6. Test plan
Unit: each diagnostic rule on synthetic evidence (positive, negative, contradictory); frame -> symbol mapping; claim validator; submit_patch schema (bad op, oversize, missing file, 0 and 2 matches, disambiguation, syntax error, atomic all-or-none);
truncation recorded and not cached; FeedbackItem constructor rejects hidden; guard v2: shared visible name allowed in a feedback span, same name outside a span blocked, hidden-only name / hidden file / path / hidden assertion blocked, no
visible dirs => unchanged. Property test over all 151 cases: for every case, guard v2 passes the real F1 feedback built from the reproducer output and fails each hidden-only marker. Integration (fake model): L0/G0/L1/G1 produce
distinct request logs, F1 attempt 2 carries the visible output, F0 does not, attempt index and replicate index are separate. No-model regression: diagnose prompts for existing v4 runs render byte-identically under `pipeline_version=v4`.

## 7. Compatibility and migration
- `pipeline_version` field (`patch_v3`, `patch_v4`, `v5`) in run_meta and records, in the cache key and in `prompt_hash` inputs; v3/v4 code paths stay selectable and their tests pass unchanged.
- Existing result directories untouched; the reader treats a missing version as the one implied by the run id (`v4*` / `fb` / `pilot8`), never inferred as v5. v5 runs use new run ids (`...-v5-...`) and a new results subtree labelled by version.
- Hidden suite stays once per case, replicate and attempts semantics unchanged (3 attempts inside a replicate; 3 replicates are separate runs, none yet done).
- **Attribution (research integrity):** run a 2x2 over the *pipeline* factor as well. Minimum: v4 vs v5 on the same cases at L0 (isolates the architecture), then v5 L0/G0/L1/G1 (graph and feedback effects inside v5). Do not compare v5-G1 with v4-L0.
  Component ablations (symptom only; + findings; + reproducer frames; + structured patch) are possible on a handful of dev cases but each costs tokens; propose symptom-only and structured-patch as the two cheap ones.

## 8. Token-cost estimate (hypotheses, not measurements)
Diagnose prompt grows by symptom (~60 tokens) + findings (~200) + visible failure (~500-1000 tokens, capped); per diagnose call +0.8-1.3k input, x up to 6 calls = up to ~7k per case (baseline ~30k for an abstaining case today).
Structured patch: output ~100-300 tokens when it works; retry on truncation up to +1 request. Estimated per case-condition 35-45k; four conditions share cached prompts where identical (G and L share when contexts are identical).
A 10-case dev check of v5 at L0 only is about 400k tokens, about 17% of the 2.4M ceiling headroom; do not run until approved. Pre-check: ledger now 837,933 committed (ceiling 2,400,000; reserve untouched).

## 9. Risks and unresolved decisions
- **D1** Is the baseline visible-reproducer failure output permitted as *diagnosis* evidence for all conditions? (It is visible test execution output; it makes the model's job easier and removes the "no-frame" regime in which L and G were equal.) Needs your approval as a methodology change.
- **D2** Accept that G vs L will now differ on most cases (previously identical on ~9/12)? This is the experiment's intended contrast but changes its power and must be reported as v5 only.
- **D3** Retry policy for truncation (same-attempt retry, counted in the 3 attempts) and whether `reasoning_effort="low"` is acceptable for patch stage (or all stages).
- **D4** Guard v2 hidden-assertion fingerprints: false-positive risk with shared numeric literals; start report-only, then enforce?
- **D5** Budget: authorise a bounded probe (~40k tokens) for output limits and structured-output support before building `submit_patch`.
- Risk: deterministic rules are generalisations, but with 151 cases mostly behavioural the gain is concentrated in the reproducer-frame localisation, not in the rule list; the rule list is cheap and safe but is not where most of the improvement should be expected.
- Risk: claim validation can reject correct but loosely-evidenced diagnoses, increasing abstention. Measure on dev before enabling.
- Unverified: AxForge output limit, schema enforcement, whether tool-call arguments escape the reasoning budget.


## Correction (24 Nov 2026, from diagnosis-root-cause-report.md)
Section 3.A item 3 and root cause A.6 say reproducer frames can be mapped to source. That holds for exception tracebacks (Redis family) but **not for value faults**: the failing frame of an
assertion is the test line (/reproducer/test_symptom.py:7), so there is no app frame to anchor on. Localisation of such faults must come from the symptom text matched to tests/symbols plus graph
expansion (tests_covers), which is why the root-cause report ranks "symptom in the prompt" and "symptom-derived retrieval with test anchors" first. Also: the 600-character rationale cap rejected the
final submission in all three budget_exhausted cases; this is a harness defect to fix inside v5.
