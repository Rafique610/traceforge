# GLM-5.3-Flash free (BeatAPI): real smoke evaluation, STOPPED at request 1 (2026-11-22)

## Outcome
The harness was built and verified, but the live evaluation **stopped on the very first model request** per the zero-cost stop rule. No task produced model output, so there are **no root-cause, repair, regression, self-correction or tool-use results**. Nothing is claimed about the model's ability.

## The stop condition
- Task T1, request 1 (`glm-5.3-flash-free`, temperature 0, max_tokens 6000, tool schemas attached, 2 messages).
- HTTP **503** `upstream_timeout`: "The generation took too long and was stopped on our side. Retry in a moment." No `Retry-After` header. Not retried, no model switch, no fallback (as required). Recorded in `spikes/glm_beatapi_eval/results/STOPPED.json` and `llm_calls.jsonl`.
- Live requests that succeeded: 0. Live attempts: 1 (failed). Cap 60 not approached.
- Probable cause (not verified): a reasoning model with a 6000-token output budget and tools exceeded BeatAPI's server-side generation time limit. Phase 1 used max_tokens 512 and responded in ~2 s. A lower max_tokens (the brief requires >= 2000) might avoid it, but that is a design change I did not make unilaterally after a stop.

## Usage endpoint (GET /v1/usage, read-only)
Snapshots in `results/usage_snapshots.json`: at start and after the 503, `credit_balance` 0, `credits_settled` 0, `by_model` only `glm-5.3-flash-free` (tasks 2, settled 0). The failed request was not counted. No paid usage, no other model.

## What was built and verified (spikes/glm_beatapi_eval/)
- `worktree.py`: disposable `git worktree add --detach` under D:/AI/tmp/eval_wt, bug injection, stripping (docs, runs, spikes, .memory, .git file, non-source backend entries), target tests removed from the visible tree and kept as scorer-only files, forced cleanup + prune. No worktrees left behind (`git worktree list` shows only the main repo).
- `sandbox_exec.py`: pytest inside the existing TraceForge sandbox isolation (network none, read-only fs, tmpfs, cap-drop ALL, non-root, memory/pids limits; tree mounted read-only; image built once from python:3.12-slim with pinned backend deps).
- `tools.py`, `agent_loop.py`: list_dir/read_file/grep/apply_edit/run_tests/submit_final with an edit policy, 14-request cap, global 60-live-request cap, STOP on any endpoint error.
- `usage_guard.py`: aborts on any paid usage or any other model, or an unreadable usage endpoint.
- `scoring.py`, `run_eval.py`, `make_tasks.py`, `tasks/T1..T4.json`: ground truth, hidden checks, mutation scoring for T4.
- Harness unit tests (scripted fake chat, labelled as test doubles): **31 passed** (tool dispatch, edit policy refusing .git/docs/hidden paths, request cap, stop-on-error, usage-guard abort, worktree cleanup for all four tasks).

## Baseline evidence (real, in the sandbox, `results/baseline_T*.json`)
All four reconstructions reproduce: the buggy tree fails the hidden target test and the fixed reference tree passes it.
| Task | Buggy: hidden target | Fixed reference |
|---|---|---|
| T1 | `..._not_labelled_verified` fails (the "keeps verified caveat" test passes on buggy code, as expected) | both pass, 12/12 reports tests |
| T2 | hidden test fails | passes |
| T3 | hidden test fails | passes |
| T4 | my scorer test fails (21 failures incl. existing gateway tests, which use a fake choice without finish_reason) | passes |

Environment note: in `tests/agent` about 12 tests fail even on the fixed tree because the sandbox image has no `git` binary and no lab data. They are recorded as environment-only failures and excluded from regression scoring; the system prompt tells the model about this.

## Limitations / honesty
- `_UNVERIFIED` text remains in builder.py after the T1 revert (an unused constant), which is a mild cue for T1. `support.py` helper `unverified_incident` is also visible.
- T4: the existing gateway tests fail on the buggy tree, which itself points at the bug.
- Root-cause scoring is keyword-based and needs human review; this was never exercised live.
- Comparison with local Qwen 7B (0/4 cause classes on seed cases) and Nemotron 3 Ultra :free (2/3 smoke tasks): not directly comparable, and no GLM numbers exist yet.

## Verdict
No verdict on the model. The free endpoint returned a 503 `upstream_timeout` on the first agentic request. To continue, the owner must decide whether to rerun (`cd backend; .venv\Scripts\python.exe ..\spikes\glm_beatapi_eval\run_eval.py`, resume-friendly via the response cache) with a smaller `MAX_TOKENS` (e.g. 2500-3000) in `run_eval.py`.
