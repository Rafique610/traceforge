# TraceForge model access report (Phase 1), 2026-11-22

Goal: which of the 7 requested models can be used through a genuinely free ($0, no card, no pay-as-you-go) cloud API, verified by a real request where free access was confirmed. Nothing was spent: key usage stayed $0 and the free-request counter stayed 49/50 across all tests. API keys are never recorded here. Evidence logs: `TraceForge_Model_Test_Logs/`.

## Verified by real requests (OpenRouter, project key with a $0 limit, 2026-11-22)
Each request: `max_tokens 16, temperature 0, "Reply with the single word: ok"`. The account identifier in the error bodies was dropped from the log.

| Requested ID | Catalog / endpoints | Real request result |
|---|---|---|
| `z-ai/glm-5.2:free` | not in `/api/v1/models`; `/endpoints` lists 0 | **HTTP 404** "This model is unavailable for free. The paid version is available now - use this slug instead: z-ai/glm-5.2" (97 ms) |
| `qwen/qwen3-coder:free` | not in catalog; 0 endpoints | **HTTP 404**, same message, paid slug `qwen/qwen3-coder` (85 ms) |
| `deepseek/deepseek-v4-flash:free` | not in catalog; 0 endpoints | **HTTP 404**, same message, paid slug `deepseek/deepseek-v4-flash` (80 ms) |
| `deepseek/deepseek-v4.1-flash-1017:free` | not in catalog; 0 endpoints | **HTTP 404**, same message, paid slug `deepseek/deepseek-v4.1-flash-1017` (101 ms) |
| `mistralai/devstral-2512:free` (earlier request, same day) | not in catalog; 0 endpoints | **HTTP 404** "The free Devstral 2 2512 period has ended" |

Kimi K3 and Kimi K2.7 Code have **no `:free` variant** on OpenRouter (paid only as listed: `moonshotai/kimi-k3`, `moonshotai/kimi-k2.7-code`). No request was sent, because it would be a paid endpoint.

## Per-model classification (all 7)
| # | Model (requested ID) | Class | Best route found | Why |
|---|---|---|---|---|
| 1 | GLM 5.2 `z-ai/glm-5.2:free` | **PAID API, NOT ELIGIBLE** (OpenRouter `:free`: DEPRECATED / ENDPOINT REMOVED, HTTP 404) | none | Z.ai direct: GLM-5.2 $1.40/$4.40 per 1M (only the -Flash models are free); Cloudflare: paid, page marked deprecated 11/20/2026; Ollama Cloud: paid; Alibaba free quota removed 2026-10-29 |
| 2 | Qwen3 Coder 480B A35B `qwen/qwen3-coder:free` | **DEPRECATED / ENDPOINT REMOVED** on OpenRouter (HTTP 404); other routes **SIGN-UP / VERIFICATION REQUIRED or UNVERIFIED** | NVIDIA Build trial endpoint (unverified; Pakistan phone-verification blocker), ModelScope (real-name verification) | Alibaba free quota removed; Cloudflare, Cerebras, SambaNova don't list it; Hugging Face paid |
| 3 | Qwen3 Coder 30B `qwen3-coder-30b` (Synap by Linkrra) | **SIGN-UP REQUIRED: free API stated by the provider, NOT yet API-verified by us** | `https://synap402.com/v1` | Official pages state a free key (Google sign-in, no card). Limits conflict between its pages: 100K tokens/day for 7 days then 50K, 50 then 10 requests/day, 4,096 max output. Pakistan eligibility unverified. Unproven small provider; usage records kept up to 24 months. A real request needs your sign-in and key |
| 4 | DeepSeek V4 Flash `deepseek/deepseek-v4-flash:free` | **DEPRECATED / ENDPOINT REMOVED** (HTTP 404); otherwise **PAID API** | none | DeepSeek direct: the legacy `deepseek-v4-flash` id is served by V4.1 Flash and billed; Cloudflare `-0731` paid; Alibaba free quota removed |
| 5 | DeepSeek V4.1 Flash 1017 `deepseek/deepseek-v4.1-flash-1017:free` | **DEPRECATED / ENDPOINT REMOVED** on OpenRouter (HTTP 404); elsewhere **FREE CHAT ONLY, NO VERIFIED API** | OpenCode "DeepSeek V4.1 Flash Free" (app only, zero retention); Puter.js free monthly allowance (size unpublished; server-side use unverified) | OpenCode docs: free models "require OpenCode"; its API key flow needs billing details. Puter: user-pays; free accounts cannot use the OpenAI-compatible endpoint |
| 6 | Kimi K3 | **PAID API, NOT ELIGIBLE** | none | OpenRouter paid; Moonshot pay-as-you-go ($1 minimum recharge; the voucher is mainland-China-number only and the sources conflict); Ollama Cloud $3/$15; Alibaba quota removed 2026-11-15; Cloudflare doesn't list it |
| 7 | Kimi K2.7 Code | **PAID API, NOT ELIGIBLE** (partly deprecated) | none | OpenRouter paid; Cloudflare paid and deprecated 11/20/2026; Moonshot K2 series closed to new users 2026-10-31 |

## Other routes checked (not among the 7 but relevant)
- OpenRouter free models that DO work: `nvidia/nemotron-3-ultra-550b-a55b:free` (verified live), ERNIE 5.5 Flash Preview, Gemma 4, Particle-1 and others (see earlier reports). 50 requests/day, 20/min.
- NVIDIA Build lists `kimi-k3.1-pro` and `glm-5.3-flash` (not the exact requested models). Pakistan (+92) phone verification is a reported blocker (forum threads Jun-Sep 2026); no workaround is suggested.
- Ollama Cloud serves kimi-k3, kimi-k2.7-code, glm-5.2 and deepseek-v4.1-flash:1017, but the account allowance is $0 and every model is billed per token: not free.
- Cloudflare Workers AI gives 10,000 Neurons/day free, but these large models say "Paid access required".

## Source URLs
OpenRouter catalog and endpoints: https://openrouter.ai/api/v1/models . Synap: https://synap402.com/free.html , https://synap402.com/models.html , https://synap402.com/terms.html , https://synap402.com/privacy.html . Alibaba: https://www.alibabacloud.com/help/en/model-studio/new-free-quota . Z.ai: https://docs.z.ai/guides/overview/pricing . DeepSeek: https://api-docs.deepseek.com/quick_start/pricing . Moonshot: https://platform.kimi.ai/docs/pricing/chat . Cloudflare: https://developers.cloudflare.com/workers-ai/models/ . OpenCode: https://opencode.ai/docs/zen/ . Puter: https://docs.puter.com/user-pays-model/ . Ollama: https://ollama.com/pricing . NVIDIA forum: https://forums.developer.nvidia.com/t/phone-verification-not-available-for-pakistan-92-blocks-api-key-generation/378993

## Confidence
High that the four OpenRouter `:free` IDs are dead (direct 404s). Medium-high (about 80-85%) that GLM 5.2, Kimi K3, Kimi K2.7 Code and DeepSeek V4 Flash have no free route. Medium for Synap (provider claim, request not yet tested, unproven operator). Low for Puter and OpenCode API behaviour (the research agents made no calls).
