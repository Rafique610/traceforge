# GLM-5.3-Flash free via BeatAPI: Phase 1 report (2026-11-22)

Scope: Phase 1 only (smoke test). The larger TraceForge evaluation (Phase 3) has NOT started and waits for Ruhan's approval. Nothing was committed or pushed.

## Configuration used
- Provider: BeatAPI. Base URL `https://direct.beatapi.io/v1` (the fallback `https://api.beatapi.io/v1` is used only if the first host is unreachable; it was not needed). Endpoint `POST /chat/completions`. Auth `Authorization: Bearer $BEATAPI_API_KEY` from the git-ignored `.env`; the key is not recorded anywhere (verified: the key string does not appear in the log).
- Model id sent in every request: exactly `glm-5.3-flash-free`. The script hard-refuses any other id (the paid siblings `glm-5.3-flash`, `glm-5.3`, `glm-5.3-flashx` can never be sent). No `/v1/responses` call. No other model, no retries other than honouring Retry-After once.

## Results
| Test | HTTP | Latency | Response `model` | Result |
|---|---|---|---|---|
| Minimal chat ("Reply with the single word: ok") | **200** | 2.32 s | `glm-5.3-flash-free` | content "ok", finish `stop`; usage 19 prompt + 46 completion tokens, **all 46 completion tokens were reasoning tokens** |
| Tool call, first attempt | **429** `rate_limit_exceeded` | 1.08 s | n/a | sent too soon after the first request; message: "at most 1 successful requests per minute per account. Retry after 60 seconds"; `retry_after_seconds: 60`. A failed request gives its slot back; no charge |
| Tool call, after waiting 66 s (Retry-After respected) | **200** | 2.30 s | `glm-5.3-flash-free` | **native tool call**: `get_service_status({"service":"worker"})`, finish `tool_calls`; usage 164 + 40 tokens (28 reasoning) |
Streaming: not tested (not needed: the TraceForge gateway does not stream; BeatAPI documents streaming support).

## Findings
- **API works for this exact free ID** with a zero-balance, never-topped-up account (2 successful requests).
- **Zero cost:** the responses contain no cost or billing fields, so zero cost is confirmed only indirectly: the documented free ID has no per-token price, the account has no balance and no top-up, and no paid ID was sent. I could not read the account balance through the API (no endpoint known); check the dashboard to confirm it still shows $0.
- **Rate limit:** 1 successful request per minute per account before the first top-up (error text quoted above); no daily allowance is promised. That is up to about 60 requests an hour, more than OpenRouter's 50 per day, but slow and strictly sequential.
- **Reasoning consumes the output budget:** even "ok" cost 46 reasoning tokens. The gateway default (4096 max output tokens) is adequate, but small caps would truncate answers.
- **Tool calling:** works natively; arguments returned as a valid JSON string.
- **Free-credit trap (from BeatAPI's public free-tier list):** an account that holds free credit can also call paid models such as claude-sonnet-5-5, gemini-3.8-flash and glm-5.3-flash. A TraceForge BeatAPI profile must therefore refuse every id that does not end in `-free`, exactly like the OpenRouter `:free` guard.
- **Docs caveats (BeatAPI free-models page):** no published context or output limit for the free ID; reasoning/`reasoning_effort` behaviour not guaranteed; `/v1/responses` unsupported; the free model "can be rate limited or withdrawn at any time"; BeatAPI's terms and privacy pages returned 404, so data retention is unknown. Use synthetic or public fixtures only.
- **Pakistan:** the account was created and a key issued, so sign-up works for Ruhan; regional availability otherwise unverified.

## What this does NOT show
A hello-world and one tool call are not evidence of coding ability. Root-cause accuracy, multi-file repair, regression tests, self-correction, abstention and misleading-log resistance are all untested. Claude Sonnet 5.5 remains the reference and nothing here suggests parity.

## Practicality for the larger evaluation (proposal, awaiting approval)
- One request per minute means the fixed 8-task smoke set (about 13-53 requests per pass) takes roughly 15-60 minutes per pass, and the 4 seed cases through the real pipeline (several calls each) about an hour per condition. Feasible if scheduled sequentially; not suited to the full 2x2x3 experiment.
- Needs a small gateway change (a free-only `beatapi` profile: base URL, `-free` suffix guard, 65 s pacing). I will ask before editing the gateway.
- Same tasks and criteria as the Nemotron and Qwen runs, on a disposable worktree; existing results are preserved.

## Recommendation (Phase 1 only)
API verified and tool-calling compatible: **continue testing**. Adoption depends on the real TraceForge tasks (Phase 3).

Raw log: `phase1_log.json` (statuses, latencies, token usage; no key). Script: `phase1_smoke.py`.
