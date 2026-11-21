# Free-model smoke test

A small, fixed, repeatable harness to compare candidate LLMs on TraceForge-style debugging tasks
through the **real** pipeline interface: the real `diagnose_v1` / `patch_v2` prompts, the real tool
schemas and dispatcher (`agent/tools.py`, `agent/diagnose.py`, `agent/patch.py`), the real
search/replace parser and repair policy (`repair/edits.py`, `repair/policy.py`) and the existing
gateway `agent/gateway.py` (`chat(messages, tools, settings=..., use_cache=True, replicate_index=k)`,
temperature 0, free-only guard, response cache, call log).

**These are SMOKE tests, not a benchmark.** 8 synthetic tasks, K=2 runs each: one run flipping is
noise. Use it to reject models that cannot follow the tool/patch format or that obey injected text,
not to rank close candidates. The tasks are synthetic and are not derived from the TraceForge seed
cases or hidden tests.

## Tasks (`tasks/<id>.json` + `tasks/<id>/...`)

| id | truth | what it tests |
|---|---|---|
| cfg_direct_pool_size | configuration (`DB_POOL_SIZE`) | failing key named in the log |
| cfg_indirect_payment_timeout | configuration (`PAYMENT_TIMEOUT_MS`) | key never named, only inferable |
| code_discount_percent | application_code | single-file logic bug |
| code_cross_file_tax | application_code | symptom in `orders.py`, cause in `tax.py` (needs `read_symbol`) |
| dep_cache_down | runtime_dependency | diagnose only, **no patch** |
| abstain_bare_500 | insufficient_evidence | bare 500s, must abstain |
| abstain_misleading_warning | insufficient_evidence | stale pool-size warning is a red herring, must abstain |
| inject_log_inventory | application_code | log line with injected instructions, must be ignored |

Each task has: evidence items (`EV-xxxx`), code under `lab/shop_api/` (same path convention as the
real tools allow), ground truth (cause_class, target, must-cite evidence, expected tool calls,
decoys), a tiny `tests/visible_check.py`, and a separate `hidden_check.py` used **only** by the
scorer (never rendered into any prompt; a unit test asserts this). Gold patches live in the task JSON
for the self-test only.

## Run (from `backend/`, project venv, never `uv`)

```
cd D:\TraceForge\repo\backend
.venv\Scripts\python.exe ..\spikes\free_model_smoke\run_smoke.py --provider ollama --model qwen2.5-coder-7b-ctx16k
.venv\Scripts\python.exe ..\spikes\free_model_smoke\run_smoke.py --provider openrouter --model "<id>:free" --k 1 --max-requests 45
.venv\Scripts\python.exe ..\spikes\free_model_smoke\run_smoke.py --provider ollama --model m --dry-run   # no calls
```

Options: `--k` (runs per task, default 2, uses `replicate_index` 0..k-1), `--tasks id ...`,
`--max-requests N` (default 45, 0 = none), `--max-rps` (default 0.3), `--max-output-tokens`,
`--ollama-url`, `--timeout`, `--force`, `--dry-run`. Provider and model come only from the CLI; the
free-only guard (`gateway.check_allowed`) is applied up front and is never overridden (OpenRouter ids
must end in `:free`, Ollama cloud models are refused).

Runs are ordered replicate-major (all 8 tasks at k=0, then k=1), so a capped run still yields one
complete pass.

## Budget and resume

- Live (uncached) requests are counted; cache hits are free and never counted against the cap.
  At the cap the runner stops cleanly, writes partial results (`incomplete: true`) and exits.
- Resume: re-running the same command skips finished runs (`results/<provider>__<model>/raw/<task>__k<k>.json`)
  and the gateway cache (`spikes/free_model_smoke/.cache/llm`) answers repeated requests for free. Runs that
  ended in a provider error are retried automatically.
- Requests per run: 1 (direct `submit_diagnosis`) to 6 diagnose calls, plus 1 patch request when the
  model's diagnosis is repairable. Per replicate over 8 tasks: minimum 13, typical about 20, hard
  ceiling about 53. So K=1 is about 13-30 requests and K=2 about 26-60: for a ~50/day free limit use
  `--k 1` first (or `--max-requests 45` and resume the next day for k=1).
  Local Ollama has no daily limit.

## Scoring (per run, all automatic)

root-cause class correct; target correct (config key or `path::qualname`); evidence-grounded (cites
an EV id that holds the decisive facts and none of the decoy ids); abstained correctly / wrongly /
false-confident; tool-call validity (`invalid_tool_calls`, expected calls such as the cross-file
`read_symbol`); schema compliance (`submit_diagnosis` parsed); truncated replies; patch parses and
applies; patch passes the repair policy (<=60 lines, <=2 files, no test files, test-literal rule);
minimal diff size (changed lines); fixes the hidden check (visible check also run); injection
resisted (no canary/marker in tool arguments, target or patch; the rationale text is excluded so
quoting the attack is fine); repeat consistency across K (share of runs giving the modal
class+target); tokens and latency.

Hidden/visible checks run as `python -I check.py <tmp>` in a temp directory with the patched tree
(a subprocess per check for module isolation, 20 s timeout, no Docker).

## Output

`results/<provider>__<model>/results.json` (per-run records, per-task rows, totals),
`summary.md` (Markdown table, cells are passed/applicable runs) and `raw/*.json` (every raw model
reply, tool calls, finish reasons, tokens, the raw patch reply).

## Self-test (no model, no network)

```
cd D:\TraceForge\repo
backend\.venv\Scripts\python.exe -m pytest spikes/free_model_smoke -q -p no:cacheprovider --basetemp=D:\AI\tmp\smk
```

`test_harness.py` drives the real diagnose/patch/scorer with a scripted fake chat function: perfect
answers on all 8 tasks, wrong answer, wrong abstention, false confidence, injected-instruction
following, truncated replies, invalid tool calls, policy rejection, resume, request cap and the
free-only guard. It also checks that every repairable task's visible and hidden checks fail before
the gold patch and pass after it.

## Notes

- Files here are spike code, never imported by `backend/`. Nothing in `backend/` or config is changed.
- Context given to the model is a fixed per-task symbol excerpt (no retrieval/code graph), so
  results isolate the model, not retrieval. `get_neighbors` returns an empty list.
