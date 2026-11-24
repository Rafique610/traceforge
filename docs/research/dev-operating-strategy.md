# Operating strategy: development vs controlled evaluation, and the two providers (adopted 24 Nov 2026)

Purpose: development never stops when AxForge is unavailable, and no controlled result is ever contaminated by development activity or by a provider swap. This changes how work is run, not the research methodology: L0/G0/L1/G1 keep their definitions, patch_v3/v4 results are untouched, the frozen test split is not used.

## 1. Two kinds of work
| | Development work | Controlled dev-d1 evaluation |
|---|---|---|
| Goal | build, debug, test, analyse | produce the measurements the plan was frozen for |
| Provider | local first; BeatAPI `glm-5.3-flash-free` for routine model tests; AxForge `glm-5.3-flash` when available | **AxForge `glm-5.3-flash` only, both arms** |
| Split / tier | dev split only; tier `development` | dev split only; tier `development` (dev-d1 is never official) |
| Run ids | `dev-<provider>-...` | `dev-axforge-{L0,G0}-dd1-l1`, `...-dd1-ctrl` (frozen in `results/screening/v5-level1-frozen.json`) |
| May change code between runs | yes, and it is recorded | no change to prompts, schema, retrieval or settings once a comparison pair has started, except documented defect fixes |

## 2. What is done locally, with no model request
Unit and integration tests, the full backend suite, Ruff, retrieval analysis (`retr_cmp`, `compare.py`, offline gold scoring), evidence processing, symptom parsing, diagnosis scoring (`traceforge/evaluation/diag_eval.py`), artifact inspection, prompt dry-runs with the leak guard (no send), cross-provider design.

## 3. Rules that keep validity
1. **No substitution.** A run id is bound to provider, model and pipeline in its `meta.json`; the runner now **refuses** to resume it with a different binding (`ValueError: run_id exists with a different provider/model/pipeline`, tested). L0 and G0 of one comparison never use different providers.
2. **Labels everywhere.** Run-level `meta.json` and per-case `run_meta.json` record provider, model, tier, `pipeline_version`, `dev_config` (dev-d1), `diagnose_only`, symptom status and the prompt hash of the pipeline actually used (v5 prompts, not the formal ones). `usage_report` now splits AxForge spend into development and official-or-unattributed by run id.
3. **Failures are not results.** Provider failures stay `provider_error` artifacts (no record). A halted run is resumed only with the same run id and binding.
4. **No wasted requests.** AxForge requests are paced at 2 per minute (>= 30 s between starts, shared by every worker, process and resume; see `axforge-pacing-audit.md`). While AxForge returns 429: no probing, no automatic retries, no retry loops. After a failure the supervisor stops; the next attempt is a deliberate single resume of the same run id (it is also the probe). BeatAPI keeps its own pacing (one request at a time, at least 90 s apart, halt on the first failure).
5. **No cache replays as runs.** dev-d1 sends live requests only; a G0 whose prompt equals its L0 prompt is not possible to hide because nothing is cached, and identical-prompt pairs are reported as such.
6. **Budget.** AxForge ceiling 2.4M and 600k reserve are enforced by the ledger; BeatAPI is a separate ledger and never counts toward AxForge; no paid fallback.
7. **Separate experiments stay separate.** The cross-provider experiment is its own design (`cross-provider-evaluation-design.md`), not run, not mixed into the primary comparison.

## 4. Provider roles
- **AxForge `glm-5.3-flash`**: the controlled comparison; official-tier model for the formal work. Currently intermittent (429/502/504).
- **BeatAPI `glm-5.3-flash-free`**: a different model id (the `-free` variant; its equivalence to AxForge's model is **unverified**), free, about one request per minute. Allowed for development-only model tests: prompt/parse smoke checks, tool-call format checks, debugging a run end to end. Its results are labelled `dev-beatapi-...`, never enter the primary comparison, and never stand in for an AxForge arm.

## 5. Procedure to resume the controlled evaluation
1. Verify the ledger (`python -m traceforge.evaluation.usage_report`; check `tokens_by_tier`).
2. Run `bash scripts/dd1_l1_eval.sh` (same run ids). It skips finished cases (014 L0 is kept), halts on the first failure, and does not loop.
3. Score with `python -m traceforge.evaluation.diag_eval --manifest ../datasets/manifests/dev.json --run L0=... --run G0=...`.
