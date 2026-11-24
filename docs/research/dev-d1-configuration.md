# dev-d1: the development-track pipeline configuration (pipeline_version `v5`)

Status: implemented and unit-tested 24 Nov 2026; first model run pending (3-case L0 smoke stage). Approved by the owner as a development configuration, **separate from the formal L0/G0/L1/G1 pipeline** (formal = `v4`, patch_v4, unchanged and still the default).

## How it is selected and kept apart
- Only with `--pipeline v5` on the experiment runner. Default is `v4`.
- The runner **refuses** `--pipeline v5` unless `--split dev` and `--out` is under a `development` directory (the frozen test split and `results/official` cannot be reached), and refuses `--diagnose-only` without v5 (`tests/evaluation/test_v5_runner.py`).
- v5 runs are always tier `development`, whatever the provider.
- Every request is **live**: `use_cache=False`, nothing is read from or written to the response cache, so no run is a replay. (v4 behaviour is unchanged: cache on.)
- Records carry `pipeline_version: "v5"`; run_meta carries `pipeline_components` (with `config_id: "dev-d1"`) and `symptom_status`. `prompt_hash` is computed over `diagnose_v2 + patch_v5`; the v4 hash is byte-identical to before.
- `L0, G0, L1, G1` keep their meaning: L/G = retrieval arm, 0/1 = feedback off/on.

## Components changed (each can be evaluated apart)
| # | Component | Where | What changed |
|---|---|---|---|
| 1 | Symptom pipeline | `agent/symptom.py`, `evaluation/real_run.py`, `agent/pipeline.py` | The visible reproducer and the visible suite are run on the base commit before diagnosis; failing tests are parsed (endpoint, inputs, assertion, compared values) into evidence items (kind `issue`, `SYMPTOM...`, appended after the collected items, so existing ids are unchanged) with suite and source hash. Hidden suite never requested. `symptom_for` (gold-term scan) is not used. |
| 2 | Symptom screening | `agent/symptom.py::validate` | Fails closed on hidden-only test names/files/paths (via the leak guard) and secret patterns; a blocked symptom is not sent (`symptom_status: blocked: ...`). Offline gold-term audit lives in `evaluation/symptom_audit.py` (evaluation only). |
| 3 | Evidence labels | `agent/evidence_view.py`, `contracts/evidence.py`, `evidence/collector.py` | Items show `scope/basis` (static/declared vs runtime/observed), origin and `path:line`. A settings default is never labelled runtime; compose values are "declared, not verified"; container env is observed but "not the app's Settings object". Old bundles get labels derived from kind/path. |
| 4 | Lexical query | `retrieval/anchors.py` | Symptom terms (endpoint words, test names, assertion identifiers, no numbers/boilerplate) are added to the BM25 query in **both** arms. |
| 5 | Graph anchors | `retrieval/anchors.py`, `retrieval/routes.py`, `retrieval/retrieve.py`, `retrieval/graph_ranker.py` | **G arm only:** functions covered (`tests_covers`) by the failing visible tests, weighted by the share of failing tests, and the handler of each HTTP request found by route resolution (decorator reading; no graph nodes added). New feature flag `symptom_anchors` (off in `NO_GRAPH`, so `G == L` when all graph features are off). |
| 6 | Retrieval record | `retrieval/compare.py` | Per run `retrieval.json`: L, G, union, overlap, unique hits, symptom relevance (no gold). `evaluate` scores gold offline only. |
| 7 | Diagnosis prompt + schema | `agent/prompts/diagnose_v2.md`, `agent/tools.py` | Symptom section, labels legend, limits stated, `SubmitDiagnosisV2`: observed_symptom, reconciliation, confidence, sufficient_evidence. |
| 8 | Claim validation | `agent/tools.py::validate_diagnosis` | Must cite a SYMPTOM item; contradicting evidence needs a reconciliation; config key must appear in the evidence and in the cited items; target symbol must exist; evidence ids must exist. |
| 9 | Tool budget | `agent/diagnose.py` | 8 valid calls; a call rejected for a locally detectable violation does **not** consume the budget (cap 3 rejections; an identical repeat stops at once); a "1 call left" note; typed reasons `insufficient_evidence` / `invalid_output` / `budget_exhausted`. A rejected submission is never turned into a diagnosis. |
| 10 | Discovery | `retrieval/sources.py`, `agent/tools.py` | `workspace_files` index in the prompt, `search_code` tool, "did you mean" on a missing symbol; service workspace only (no tests, other services or hidden material). |
| 11 | Hand-off | `agent/handoff.py`, `repair/scope.py`, `repair/loop.py` | `validate_target` before any patch (abstain, never substitute); patch scope policy rejects edits outside the diagnosed key/function (`edit_outside_diagnosed_target`), addressing the 013 over-edit. Prompt `patch_v5`. |
| 12 | Diagnose-only | `agent/pipeline.py`, `evaluation/runner.py` | `--diagnose-only` stops after diagnosis (`failure_reason: diagnosis_only`, outcome NO_PATCH); no patch request is possible. |
| 13 | Run isolation | `evaluation/runner.py`, `evaluation/real_run.py` | See above. |

## Inherited interim settings (from the previous approved task, uncommitted, not part of v5 itself)
Hidden-leak guard exempts test names defined in the case's own visible tests (hidden-only names, hidden files and paths stay blocked); patch output cap 8192; truncated empty replies are not cached.

## Not changed
Formal v4 prompts, tools, schema, retrieval query, budget (6), patch prompt, policy, cache behaviour; condition definitions; the frozen test split; all existing results.

## Known limits (stated, not hidden)
- Compared values use operand order (left = produced, right = required); a heuristic.
- Route resolution reads decorators only (FastAPI/Flask-style); other routing styles are not resolved.
- The DB does not persist the new evidence fields (derived labels are used when reading from the DB).
- Claim validation can raise abstention; untested with a model until the smoke stage.
