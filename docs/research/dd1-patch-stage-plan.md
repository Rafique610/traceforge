# dev-d1 patch stage: audit and execution plan (NOT LAUNCHED)

Written 24 Nov 2026 for the owner's confirmation. No model request has been made for this audit. Scope: the six Level-1 cases (096, 182, 014, 067, 058, 085) under L0 and G0, F0 (no feedback), from the existing correct diagnoses. Controls 004 and 001 are not patched.

## 1. Frozen inputs (condition 1)
`results/development/dd1-l1-frozen-manifest.json` freezes **251 files** with sha256 (manifest sha256 `9c503e67ac07...fa6191`): all four diagnosis run directories (L0, G0, controls L0, G0) with every case's `requests.jsonl` (prompt hashes), `evidence_v5.json`, `symptom.json`, `retrieval.json`, `context_sent.json`, `diagnosis.json`, `trace.json`, records and run metadata (including the old `provider_error` artifacts), the smoke run, `dd1-l1-evaluation.json` (scores), the frozen plan file, and the eight evidence bundles used. `freeze_manifest verify` passes now. The patch runs write only to **new** run ids; the manifest is never overwritten (the build command refuses), and the launch script re-verifies it first and stops if anything changed.

## 2. How diagnoses are not regenerated (condition 2)
New mode `--patch-from <diagnosis run dir> --frozen-manifest <manifest>` (dev-d1 only; refused without `--pipeline v5`, or with `--diagnose-only`). For each case it loads the saved `diagnosis.json` and `evidence_v5.json` of the **same arm**, checks their hashes against the manifest, refuses a diagnosis that abstained or belongs to another arm, then runs the patch stage directly: no evidence collection, no retrieval, no diagnose request (unit-tested: the first and only request is the patch prompt, tool calls 0, tokens are patch-only). The saved diagnosis object is passed through unchanged; `validate_target` and the patch scope policy still run. Run metadata records `stage: patch` and the source run, diagnosis hash and evidence hash. A resumed run cannot change its source.

## 3. What the patch stage does (inspected)
- **Prompt:** `patch_v5` + the diagnosis (class, target, rationale) + the **verbatim** target files (at most 2, whole file up to 8,000 chars) + labelled evidence including the symptom. In the dry run all 12 prompts show the diagnosed file and one more editable service file that mentions the diagnosed name.
- **Edit format and application:** SEARCH/REPLACE blocks, exact single match, only files under `lab/<service>/` (not tests), then policy (size <= 60 lines, <= 2 files, test-literal check, syntax) and **scope policy**: edits must lie inside the diagnosed function (so an unrelated edit like the 013 over-edit is rejected, reason `edit_outside_diagnosed_target`).
- **Loop (F0):** up to 3 attempts, each a new live request, **no feedback** (F0 passes `None`; unit-tested). Each applied attempt runs the reproducer and the whole visible suite in the sandbox. The hidden suite runs **once** on the frozen final patch and its result is stored as counts only; hidden contents, names and outputs never reach a prompt (leak guard on every request).
- **Settings inherited:** output cap 8192 for the patch stage, truncated replies are recorded `output_truncated` (not cached; cache is off), temperature 0, live requests, 30 s shared AxForge start-to-start pacing, one request in flight, halt on the first provider failure or 429, no retries, no provider fallback.
- **New measurements (this stage):** per attempt the visible test outcomes by id and the reproducer outcomes; a baseline visible run on the base commit (sandbox only, no model); diff statistics (files, added/removed lines, base line numbers). `patch_eval.py` (evaluation only) derives: patch generated, applied, files and lines changed, reproducer/visible/hidden pass (hidden as counts), visible-suite **regressions** (passed at base, not passing after the patch; hidden-suite regressions cannot be reported by name, only pass/fail counts), tokens, request count and latency, and **fixed** (= verified: reproducer, visible and hidden all pass). Offline it also compares the patch with the gold fix (lines inside the gold function; exact equality with the reverse of the mutation), never during the run.

## 4. Dry run (no model): prompts and token estimate
All 12 patch prompts were built offline from the saved diagnoses with the current code; the hidden-leak guard accepted each, and `validate_target` returned none. Estimated input per request (the ledger's deliberately high 3-characters-per-token estimator): 4,733 to 5,533 tokens, **61,687 for the 12 first attempts**.

| Scenario (12 runs) | Tokens |
|---|---|
| Expected: attempt 1 only, ~150 output tokens (typical patch replies were 55 to 300 tokens in 67 of 70 earlier requests) | about 63k |
| Attempt 1 only, ~400 output tokens | about 66k |
| Every run uses all 3 attempts, ~400 output tokens | about 199k |
| 3 attempts, ~2,000 output tokens each (a reasoning-heavy model) | about 257k |
| **Conservative worst case: 3 attempts, every reply at the 8,192 cap** | **479,973** |
Ledger now: 1,114,772 committed, 1,285,228 remaining to the 2.4M ceiling. Even the worst case leaves **805,255** to the ceiling and does not approach the 600k reserve (which lies beyond the ceiling and is never used). Per-request reservations are about 13.5k tokens at most. The script also refuses to start a run below 700,000 remaining.
Time: at least 12 requests if every first attempt applies (about 6 to 8 minutes of pacing), at most 36 requests (at least 18 minutes) plus model latency (earlier patch requests with long hidden reasoning ran for minutes) and about 10 to 20 seconds of sandbox time per attempt.

## 5. Planned execution (awaiting confirmation)
1. `bash scripts/dd1_patch_eval.sh`: verifies the frozen manifest, then run `dev-axforge-L0-dd1-patch` (six cases, L0 diagnoses), then `dev-axforge-G0-dd1-patch` (six cases, G0 diagnoses). Separate run ids, separate directories; no mixing of arms.
2. First provider failure or 429: the run stops, the artifact stays as `provider_error`, the script stops. No retry, no switch. A resume would be a separate deliberate invocation.
3. After completion: `python -m traceforge.evaluation.patch_eval --manifest ../datasets/manifests/dev.json --run L0=... --run G0=... --out ../results/development/dd1-patch-evaluation.json`, then the report (patch generation and repair outcomes per case, site and arm). **No feedback stage** until reviewed.

## 6. Risks and limits (stated)
- The scope policy may reject a correct multi-line fix that touches lines outside the diagnosed function (recorded as a rejected attempt with its reason; it is a measured effect of the dev-d1 configuration, not tuned on these cases).
- Output truncation from hidden reasoning is possible (earlier 3 of 70 patch requests hit the old 4096 cap); recorded, not repaired.
- One sample per cell; the model is not deterministic at temperature 0.
- The visible suite regressions are exact by test id; hidden-suite regressions are visible only as counts.
- The diagnoses expose the gold function name through the symptom; the patch stage inherits that.
- Docker/sandbox errors would be recorded as `sandbox_error`/UNVERIFIED, not as failures of the model.
