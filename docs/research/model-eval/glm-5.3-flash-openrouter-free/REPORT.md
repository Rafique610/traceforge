# GLM-5.3-Flash (`z-ai/glm-5.3-flash:free`) on OpenRouter: integration and evaluation report (2026-11-22)

## Verdict: STOPPED at the connectivity gate. The exact free endpoint does not exist. Nothing else was tested.
Per the task rules ("if the free endpoint returns 404 ... STOP and report; never switch to a paid model"), no evaluation task was run, nothing was scored, no paid ID was called, and no money was spent (key usage $0 before and after; free-request counter 49/50 before and after).

## Pre-test verification of the exact model ID and pricing
| Check | Result |
|---|---|
| `z-ai/glm-5.3-flash:free` in the live catalog (`GET /api/v1/models`, 476 models) | **no** |
| Provider endpoints for it (`/api/v1/models/z-ai/glm-5.3-flash:free/endpoints`) | **0 endpoints** |
| Free-priced models in the catalog right now | 11 text models (ERNIE 5.5 Flash Preview, Gemma 4 26B/31B, Ling 3.2 Flash, LFM 3 1.7B, Nemotron 3 Nano Omni / 3 Ultra / 3.5 Lightning / 3.5 Super VL, Particle-1, Flint v1.0). No GLM. |
| Paid sibling `z-ai/glm-5.3-flash` | exists, **not free**: listed $0.0000000399 input / $0.0000000784 output per token (about $0.04 / $0.08 per 1M). Not called. |

## API connectivity test (one minimal request to the exact free ID)
- Request: `POST https://openrouter.ai/api/v1/chat/completions`, model `z-ai/glm-5.3-flash:free`, `max_tokens 16`, `temperature 0`, prompt "Reply with the single word: ok". Key read from `.env` (never printed).
- **HTTP 404**, 2026-11-22: `{"error":{"message":"This model is unavailable for free. The paid version is available now - use this slug instead: z-ai/glm-5.3-flash","code":404}}`.
- Raw log (no key, no account id): `connectivity_log.json` in this folder.
- Not testable because no response was returned: the returned model id, reasoning support, tool calling, streaming, structured JSON reliability, rate limits.

## Requested tests: not run (blocked by the 404)
| # | Task | Status |
|---|---|---|
| 1 | Root-cause analysis of a genuine bug | NOT RUN |
| 2 | Multi-file repair | NOT RUN |
| 3 | Backend/frontend/DB/investigation relationships | NOT RUN |
| 4 | Regression tests that reproduce the bug | NOT RUN |
| 5 | Running tests and interpreting failures | NOT RUN |
| 6 | Correcting its own changes | NOT RUN |
| 7 | Misleading logs vs real causes | NOT RUN |
| 8 | Tool calls and repository instructions | NOT RUN |
Root-cause accuracy, repair success rate, regression rate, tool-use reliability and token usage: **N/A**. Comparison with existing results (kept unchanged, nothing overwritten): local Qwen2.5-Coder 7B got 0/4 cause classes with the real pipeline; Nemotron 3 Ultra `:free` passed 2 of 3 smoke tasks and was fooled by the misleading-warning task. No GLM-5.3-Flash result exists to compare.

## Other possible free routes to GLM-5.3-Flash (from today's research; none verified or testable now)
- NVIDIA Build lists `glm-5.3-flash` ("z-ai/glm-5.3-flash"): free-trial terms unconfirmed, and the Pakistan (+92) phone-verification blocker is reported. No workaround suggested.
- OpenCode "GLM-5.3-Flash Free": listed as deprecated in Nov 2026 and app-only.
- Z.ai direct and Ollama Cloud: paid (about $0.15 in / $0.50 out per 1M tokens; Ollama allowance $0).
- Hugging Face: paid; Cloudflare: GLM-5.3 not free-usable.

## Recommendation
**Reject for now (not testable at $0).** Keep testing is only possible if the free endpoint returns; it can be re-checked at no cost with the same single request, or by watching OpenRouter's catalog. Hand-off: recommending a primary model still rests on `nvidia/nemotron-3-ultra-550b-a55b:free` (provisional, awaiting Ruhan's approval) with local Qwen as fallback. Claude Sonnet 5.5 reference: no free model, including this one, has been shown close on TraceForge tasks.

If you later approve a tiny paid allowance, `z-ai/glm-5.3-flash` (about $0.04/$0.08 per 1M tokens on OpenRouter) would be the cheapest strong GLM to test; that is your decision and nothing was enabled.
