# Controlled retry of the 503 `upstream_timeout` (2026-11-21, 23:26 UTC)

Authorised by Ruhan: exactly ONE additional live request with the original configuration. Nothing else was sent. No paid model, no top-up, no existing file changed, seed cases not started.

## Before the retry
- **What BeatAPI says about the error** (https://docs.beatapi.io/errors and /text-api): a 503 `upstream_timeout` is "a failure on the model's side", rewritten into the SDK shape; "a 503 has no known wait, so retry it with backoff"; its retry policy table says to retry once or twice with backoff. No status page or incident notice exists (`status.beatapi.io` does not resolve; `/status` pages 404). Also documented: `max_tokens` is used to estimate the balance a request needs, but a 6000 value is far below the level that causes 402 refusals.
- **The failed request:** 2026-11-21 23:11:33 UTC, `upstream_timeout` ("The generation took too long and was stopped on our side"), no Retry-After, request id recorded in `results/STOPPED.json`.
- **Connection timing (public GETs, no model call):** `direct.beatapi.io` DNS 0.05 s, TCP 0.38 s, TLS 1.10 s; `api.beatapi.io` DNS 0.04 s, TCP 0.06 s, TLS 0.19 s. Both hosts reachable.
- **Payload identity proven:** the retry rebuilds the request with the harness's own code and compares the gateway cache key with the failed request's key: `3c2d6194b13fe755...` identical (model `glm-5.3-flash-free`, `max_tokens` 6000, `temperature` 0, the same 6 tool schemas, the same 2 messages).
- **Waited** until 15 minutes after the failure (204 s of waiting), then the usual 65 s pacing guard applied.

## Result of the retry
| Field | Value |
|---|---|
| Sent at | 2026-11-21 23:26:33 UTC |
| HTTP result | **success** (not 503) |
| Latency | **3.6 s** |
| Response model | `glm-5.3-flash-free` |
| Finish reason | `tool_calls` (no text content) |
| Tokens | 1,055 in / 53 out |
| Tool calls returned | `list_dir({"path":"backend/traceforge"})` and `grep({"path":"backend/traceforge","pattern":"Verified only by the lab test suites"})` |
Both calls are valid JSON arguments and are sensible first steps for the T1 bug report (the grep targets the exact misleading phrase quoted in the report).

## Cost check
Verified directly with the read-only usage endpoint after the run: `credit_balance 0`, `credits_settled 0`, `credits_refunded 0`, `total_tasks 3` (the two Phase 1 requests plus this retry; the 503 was not counted), `by_model` only `glm-5.3-flash-free`. Guard `violations()` reported none. (My retry script printed nulls for the usage summary because it read the wrong JSON level; the guard itself and the direct check above are correct. The script is fixed and the saved result annotated.)

## Conclusion
The 503 was a **transient upstream problem**, not caused by the 6000-token configuration or the payload: the identical request succeeded 15 minutes later in 3.6 s. Caveats: n = 1 failure and 1 success, so intermittent upstream timeouts on this free model remain possible (BeatAPI says free models can be slower or withdrawn at any time). The evaluation itself has still NOT been run; no coding result exists. Reducing `max_tokens` was not needed to explain this failure; testing 3000 tokens would be a separate experiment, as you said.

## What I did not do
Resume the T1-T4 smoke run, change `max_tokens`, or touch the seed cases. Files: `spikes/glm_beatapi_eval/retry_once.py` (new), `spikes/glm_beatapi_eval/results/retry_once.json` (new). Nothing is committed.
