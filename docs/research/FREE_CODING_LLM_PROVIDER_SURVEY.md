# Free coding-LLM provider survey: OpenRouter and OpenCode (2026-11-21)

Research only. No TraceForge configuration, gateway or experiment was changed. No paid request, credit purchase, payment method or paid fallback. No key is printed or recorded here. Facts below were read from public catalogs/pages/APIs on 2026-11-21 unless marked **unverified**. Companion files: `FREE_CODING_LLM_REDDIT_FINDINGS.md`, `CODING_LLM_BENCHMARK_COMPARISON.md`, `TRACEFORGE_FREE_MODEL_RECOMMENDATION.md`. Earlier work: `CODING_LLM_COMPARISON.md`, `DEVSTRAL_OLLAMA_INVESTIGATION.md`.

## 0. Corrections to the candidate list
Checked against OpenRouter's live public catalog (`GET https://openrouter.ai/api/v1/models`, 476 models):
- **`thinkingmachines/inkling-small:free` does not exist.** Inkling is listed only as paid: `thinkingmachines/inkling-small` ($0.45 in / $1.20 out per 1M), `inkling-2-small` ($0.30 / $1.00), `inkling-2-mini` ($0.10 / $0.40), `inkling` ($1.00 / $4.05).
- **`qwen/qwen3.8-27b:free` does not exist.** Only paid: `qwen/qwen3.8-27b` ($0.06 in / $1.96 out per 1M).
- **No DeepSeek V4 Flash variant is free on OpenRouter** (v4-flash $0.09/$0.18; v4.1-flash $0.0498/$0.1992; -1017 $0.15/$0.60 ...). It is free only on OpenCode (see section 2) which cannot be used from our gateway.
- The catalogue changes; every ID must be re-verified immediately before use.

## 1. OpenRouter
### 1.1 What is genuinely free
A model counts as free only if its endpoint pricing is zero. From the live catalog and each model's `/endpoints` data (provider, quantization, uptime):
| Model ID | Context | Max output | Tools | Structured out | Reasoning | Single provider endpoint (quant) | 30-min uptime |
|---|---|---|---|---|---|---|---|
| nvidia/nemotron-3-ultra-550b-a55b:free | 1,000,000 | 65,536 | yes | **no** | yes | Nvidia (unknown) | 100% |
| nvidia/nemotron-3.5-lightning:free | 1,000,000 | 65,536 | yes | no | yes | Nvidia (nvfp4) | 100% |
| nvidia/nemotron-3.5-super-vl:free | 1,000,000 | 131,072 | yes | yes | yes | Nvidia | 100% |
| baidu/ernie-5.5-flash-preview:free | 1,024,000 | 921,600 | yes | yes | yes | Baidu | 100% |
| particle-ai/particle-1:free | 1,048,576 | 131,072 | yes | yes | yes | Particle AI (us) | 100% |
| recursive/flint-v1.0:free | 262,144 | 235,929 | yes | yes | yes | Recursive (bf16) | 100% |
| inclusionai/ling-3.2-flash:free | 1,048,576 | 262,144 | yes | yes | yes | Ant Digital (fp8) | 100% |
| google/gemma-4-31b-it:free | 262,144 | 32,768 | yes | yes | yes | Google AI Studio | 93.3% |
| google/gemma-4-26b-a4b-it:free | 262,144 | 32,768 | yes | yes | yes | Google AI Studio | 100% |
| nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free | 256,000 | 65,536 | yes | no | yes | Nvidia | 100% |
| liquid/lfm-3-1.7b:free | 262,144 | 8,192 | yes | yes | yes | (small 1.7B; not a candidate) | n/r |
| openrouter/free (router) | 200,000 | none | yes | yes | yes | dynamic | n/a |
Every `:free` model has **exactly one provider endpoint**, run by the model's own vendor: there is no failover, so an outage or a vendor decision removes the model. Quantization is unknown for most.
Note: the paid Nemotron-3-Ultra listing has a 262K context; the free listing says 1M.

### 1.2 Limits and billing rules (official: https://openrouter.ai/docs/api-reference/limits)
- Free variants (IDs ending `:free`) have per-minute and per-day request limits that depend on credits purchased all time. The page's own table values did not render in the fetch; earlier research recorded **20 requests/min and 50 requests/day** with <$10 purchased (documented there; **unverified here**).
- `GET /api/v1/key` returns `free_model_daily_requests` (counter and ceiling): the authoritative way to read the remaining quota without making a model request.
- "If your account has a negative credit balance, you may see errors, including for free models." Our key has a $0 spend limit and no credits.
- Per-key credit limit: ours is 0, so a paid request cannot succeed on this key.
- **Current blocker (2026-11-21):** the OpenRouter key line is no longer in `.env` (it was overwritten when the Ollama key was added), so no OpenRouter request or quota read is possible until the key is re-added.

### 1.3 `openrouter/free` router
Catalog entry: context 200K, no max-output figure, routes each request to one of the currently available free models. A request's model can differ between calls, so it is **unsuitable for controlled comparisons or reproducible experiments** (same-model requirement in `docs/invariants/ml.md`). Acceptable only for throw-away experiments. Not recommended.

### 1.4 Privacy (unverified)
Free endpoints are vendor-run (Nvidia, Baidu, Google AI Studio, Particle AI, Recursive, Ant Digital). Retention and training terms were not verified for each; Google AI Studio's free tier is reported by earlier research to use content for product improvement. Treat prompts to free endpoints as non-private; never send secrets or hidden tests (TraceForge never sends hidden tests).

## 2. OpenCode (official: https://opencode.ai/docs/zen , /docs/console/models)
- Free models listed as "free for a limited time": DeepSeek V4.1 Flash Free (zero retention, no training), MiMo-V2.6-Flash Free, Nemotron 3.5 Lightning Free, Nemotron 3.5 Super VL Free, Inkling 2 Small Free (provider retains data and may train on it), Beam Free (no training, 30-day retention), Flint 40B Free, LongCat 2.5 Free (limit **100 requests/day**), Big Pickle (data may be used to improve the model), Iceman Free (data retained and used). Free periods are temporary.
- **Programmatic access:** the page states "Free-tier chat models require OpenCode; use paid models or Go from other clients." So the free models cannot be called from our own gateway or another client.
- **API key flow:** "Sign in to the console, **add your billing details and credits**, and copy your API key." That conflicts with the no-payment-method rule, so the OpenCode Zen API route is **unsuitable** for TraceForge.
- Regions: per-model restriction lists name specific countries/regions (e.g. EU for Inkling 2 Small Free; China, Iran, Russia and others for Beam). **Pakistan is not named in any restriction on the page**; per-model availability from Pakistan is otherwise unverified.
- The OpenCode desktop/TUI app may offer free models after sign-in; that is a different tool, not a drop-in for our experiment gateway, and a TraceForge experiment run through it would not be reproducible with our cache/call log.
- Verdict: OpenCode is useful as a manual coding assistant for development, not as TraceForge's experiment model provider.

## 3. Other genuinely free routes
- **Local Ollama** `qwen2.5-coder:7b` (verified working, free, unlimited, weak/slow).
- **Ollama Cloud**: not free for this account (allowance $0; Devstral retired). See `DEVSTRAL_OLLAMA_INVESTIGATION.md`.
- **Google AI Studio (Gemini/Gemma) direct free tier**, **Groq**, **Mistral Experiment plan**: not re-verified in this pass; earlier notes in `free-model-providers.md` say limits and data terms are unconfirmed.
- GitHub Models: reported retired 2026-07-30 (earlier research).

## 4. Gateway compatibility
The existing gateway (OpenAI-compatible chat completions, tools, temperature 0, seed, replicate-aware cache, retries, free-only allowlist) already supports the `openrouter` profile for `:free` IDs. Provider-specific points:
- Reasoning models need an output budget (default now 4096, configurable) because hidden reasoning consumes tokens; truncation is reported as `output_truncated`.
- Models that print tool calls as JSON text are handled; native tool calls verified for `nvidia/nemotron-3-ultra-550b-a55b:free`.
- `structured_outputs` is not offered by the Nemotron Ultra/Lightning/Nano free endpoints; TraceForge does not rely on JSON mode (tool calls + SEARCH/REPLACE text).
- Streaming is not used by the gateway.
- Silent model changes: a vendor can swap the weights behind an ID; record the date and ID in every run.
- Each free model has one endpoint: no failover; expect outages and keep the cache.

## 5. Status of smoke tests
No OpenRouter or OpenCode smoke test was run in this pass: the OpenRouter key is missing from `.env`, and OpenCode free models cannot be called outside its app. A fixed task harness for later is being built (`spikes/free_model_smoke/`, no model calls).
