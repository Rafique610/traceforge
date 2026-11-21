# Free model providers for TraceForge (research, 2026-11-21)

Method: official pages fetched 2026-11-21 via a fetch tool that summarizes pages (not raw HTML). No signup, auth, install, or API calls were made. Anything marked **UNVERIFIED** was not stated on the fetched page. Free tiers change often; re-check the linked page before relying on any number. Model names are copied as the pages showed them; I did not confirm they exist beyond those pages.

## 1. Findings per provider

### Ollama Cloud
- Pricing page lists only "Pay as you go" at $0: no subscription, **no included monthly credits**; each cloud request is paid from purchased usage credits; 3 concurrent requests, queued then rejected beyond that. Local models are unlimited. (https://ollama.com/pricing, 2026-11-21)
- Conclusion: **not genuinely free for cloud models** (credit purchase needed). UNVERIFIED whether any free quota exists elsewhere (Usage page not read).
- Needs an Ollama account + API key; endpoint `https://ollama.com/api`; app/CLI/local API can also run cloud models after `ollama signin`. Cloud models "don't currently support structured outputs". Zero data retention, no training. (https://docs.ollama.com/cloud, https://docs.ollama.com/cloud/faq)
- UNVERIFIED: OpenAI-compat endpoint on ollama.com, `:cloud` tag syntax, context windows.

### Mistral (Vibe CLI vs La Plateforme)
- Le Chat Free plan: "limited" Vibe access; FAQ says Free includes Vibe CLI but capped by limited coding sessions (exact caps unpublished: UNVERIFIED). Training: pricing table shows "Opt-out" (column mapping to Free is inferred; confirm in terms). (https://mistral.ai/pricing)
- Vibe 2.0 announcement (2026-01-27): Devstral 2 requires paid API access; free API usage remains on the **Experiment plan** in Mistral Studio ("testing and prototyping"); Le Chat Pro/Team include full Vibe CLI + Devstral 2; BYOK supported; subscription overage can continue at API rates (paid fallback risk). Devstral 2 $0.40/$2.00 per M tokens; Devstral 2 Small $0.10/$0.30. (https://mistral.ai/news/mistral-vibe-2-0/)
- API "Free mode" is the default, lowest limits, per-org per-model, shown in Admin Console > Limits; enabling pay-as-you-go unlocks Tier 1+; prepaid credits do not change tier. (https://help.mistral.ai/en/articles/698531)
- Vibe Code Web: Free = 2 sessions/day (from a search snippet of docs.mistral.ai/vibe/code/vibe-code-web/limits-and-lifecycle; not fetched directly).
- UNVERIFIED: whether Devstral is callable on the Experiment tier today (announcement ambiguous); Experiment data-training terms; phone verification; exact RPM/TPM. The docs tier page URL returned 404.

### OpenCode / OpenCode Zen (now "OpenCode Console")
- OpenCode supports the models.dev catalog (OpenCode Go, OpenAI, Anthropic, Google, Vertex, Azure, Bedrock, OpenRouter, xAI, GitHub Copilot), local Ollama/LM Studio/vLLM, and any OpenAI-compatible custom provider. Auth via `/connect`. (https://opencode.ai/docs/providers/)
- Console page lists 12 free models (e.g. Big Pickle, Iceman Free, Inkling 2 Small Free, DeepSeek V4.1 Flash Free, Beam Free, LongCat 2.5 Free), mostly limited-time, usable only inside OpenCode. LongCat 2.5 Free: 100 req/day. Key flow says sign in, **add billing details and credits**, copy key (card need for free-only use: UNVERIFIED). Data: Big Pickle and Flint 40B Free may use data to improve the model; Iceman Free and Inkling 2 Small Free retain data (Inkling may train); Beam Free retains 30 days; Nemotron free models trial-only and logged; DeepSeek V4.1 Flash Free zero-retention; LongCat hosted in China. Some free models geo-blocked. `OPENCODE_DISABLE_FREE_MODELS=1` hides them. (https://opencode.ai/docs/zen/)
- Risk: free models rotate; paid models sit in the same picker; auto-recharge exists.

### OpenRouter
- `:free` IDs: 20 RPM; 50 req/day if <10 credits ever purchased, 1000 req/day if >=10 credits (all-time). Usage via `GET /api/v1/key`. A negative balance can break even free models. `openrouter/free` router picks a free model per request (non-deterministic; do not use for experiments). (https://openrouter.ai/docs/api-reference/limits, https://openrouter.ai/docs/faq)
- Buying credits does raise limits (50 -> 1000/day); that is a card payment, so it breaks the $0 rule.
- Silent paid fallback: dropping `:free` from the ID bills per token. Always include `:free` explicitly.
- Free-model logging/training: UNVERIFIED (FAQ: prompts not logged by default; log-capable providers excluded unless the training toggle is on).
- Current free coding models and per-model tool-calling support: **UNVERIFIED**. The models page fetched showed no `:free` models. The human must filter the catalog by Free + supported parameter "tools".

### Groq
- Rate-limit page has Free Plan and Developer Plan tabs; extraction showed only Developer base limits (e.g. openai/gpt-oss-120b 30 RPM, 1K RPD, 8K TPM, 200K TPD). Free-plan numbers: **UNVERIFIED**. Upgrading to Developer requires a payment method, implying Free needs none. Overage on Free and data retention: UNVERIFIED. (https://console.groq.com/docs/rate-limits, https://console.groq.com/docs/billing-faqs)

### Google AI Studio / Gemini API
- Free tier per project; paid requires setting up billing. Daily quotas reset midnight Pacific. Only free-tier figures seen were for "Gemini Decision 1" (200 RPM, 50K TPM, 10K RPD); full table not obtained. (https://aistudio.google.com/docs/rate-limits)
- Pricing page lists free models: Gemini 4 Hydrogen, Gemini 3.8 Flash, Gemini 2.5 Pro (deprecated; routes to Gemini 3.8 Flash on 2026-12-01), others. Gemini 4 Carbon/Argon/Neon are not free. **Free-tier content is used to improve Google products**; paid is not. (https://aistudio.google.com/docs/pricing; last ~18k chars unread)
- Context windows, OpenAI-compat endpoint, structured output, tool calling: UNVERIFIED.

### Cerebras
- "Free Trial" is not permanent: $5 credits **after adding a verified payment method**, expiring after 30 days; without a card the API stays inactive. gpt-oss-120b: 5 RPM, 30K uncached TPM, 1M TPD; qwen-3.8-27b: 300 RPM (temporarily raised). (https://inference-docs.cerebras.ai/support/rate-limits)
- Conclusion: needs a card; excluded under the $0 policy.

### GitHub Models
- **Retired**: playground, catalog, inference API and BYOK unavailable as of 2026-07-30. (https://docs.github.com/en/github-models/prototyping-with-ai-models)

### Others
- Not investigated: Cloudflare Workers AI, NVIDIA NIM, Hugging Face, SambaNova, Together. Local Ollama on own hardware is the only provably unlimited option (Ollama pricing page).

## 2. Comparison table

| Provider | Free? | Card? | Verified limits | Tools | Struct. output | OpenAI-compat | Multi-hour agent | Training/retention |
|---|---|---|---|---|---|---|---|---|
| Ollama Cloud | No (credits) | Credits | 3 concurrent | UNVERIFIED | No (stated) | UNVERIFIED | Pay-per-token | ZDR, no training |
| Mistral Experiment API | Yes, low | UNVERIFIED | Console only | UNVERIFIED | UNVERIFIED | UNVERIFIED | Unlikely | UNVERIFIED |
| Le Chat Free + Vibe | Yes, capped | No (inferred) | "limited sessions" | Agent | n/a | n/a | No | Opt-out (inferred) |
| OpenCode free models | Yes, rotating | Key flow asks billing | LongCat 100/day | UNVERIFIED | UNVERIFIED | Yes (bearer) | Varies | Varies; some train |
| OpenRouter :free | Yes | No (50/day); yes for 1000/day | 20 RPM, 50 or 1000/day | per model, UNVERIFIED | UNVERIFIED | UNVERIFIED here | OK at 1000/day | UNVERIFIED |
| Groq | Yes | No (inferred) | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | Likely tight | UNVERIFIED |
| Gemini API | Yes | No (inferred) | Table not obtained | UNVERIFIED | UNVERIFIED | UNVERIFIED | Possible | Free = used to improve |
| Cerebras | Trial | Yes | 5 RPM, 1M TPD (gpt-oss-120b) | UNVERIFIED | UNVERIFIED | UNVERIFIED | No | UNVERIFIED |
| GitHub Models | Retired | - | - | - | - | - | - | - |
| Local Ollama | Yes (own HW) | No | Unlimited | per model | per model | Yes (local; from memory) | Yes | Local |

## 3. Recommended setups

(a) Claude-Code-style dev assistance
- Primary: OpenCode with free models, non-sensitive code only; prefer zero-retention ones (e.g. DeepSeek V4.1 Flash Free). First confirm a free-only key needs no card.
- Secondary: OpenRouter explicit `:free` coding model (50/day without credits).
- Fallback: Mistral Le Chat Free / Vibe CLI (capped) or Gemini free tier (content trains Google models; no private data).

(b) TraceForge experiment runner (temp 0, tool calling, reproducibility, pinned IDs)
- Primary: local Ollama with a pinned model tag/digest. Only free, unlimited, stable option; no deprecation surprises. Hardware-dependent; model choice not verified here.
- Secondary: OpenRouter explicit `:free` ID; record returned model/provider per call. Free models rotate, so reproducibility is weak. (Provider pinning options exist in OpenRouter docs; from memory, verify.)
- Fallback: Gemini free tier with a dated, pinned model ID (not an alias); non-sensitive prompts only.
- Avoid for experiments: `openrouter/free` router, time-limited OpenCode free models, Gemini 2.5 Pro (auto-routes 2026-12-01), Ollama Cloud and Cerebras (credits/card).
- Runner design: log model ID, provider, date, seed, temperature per result; treat free backends as non-reproducible even at temperature 0; hard-fail on any non-`:free` ID.

## 4. Warnings
1. Several "free" paths need a card or credit purchase (Cerebras, Ollama Cloud, OpenCode key flow, OpenRouter for 1000/day). Do not enter payment info.
2. Silent paid fallback: OpenRouter non-`:free` IDs, Mistral subscription overage "at API rates", Groq/Gemini upgrade prompts, OpenCode auto-recharge. Never enable auto-recharge or pay-as-you-go.
3. Some free tiers train on data (Gemini free; some OpenCode models). Never send secrets or private data.
4. Free models rotate or deprecate; pinned IDs can vanish mid-project.
5. The fetch tool summarized pages and some were truncated or partial; confirm numbers in each console.
6. Keys: environment variables or a gitignored `.env`; never commit; one key per provider, no billing attached; rotate on leak.

## 5. Human sign-in steps
1. OpenRouter: create account (no card), create API key, check `/api/v1/key` usage. Do not buy credits.
2. Google AI Studio: sign in, create a key in a project without billing; read the data-use notice.
3. OpenCode: `/connect` a Console key only if it can be created without a card; otherwise skip.
4. Mistral: Le Chat Free sign-in; for API, Mistral Studio Experiment plan, accept terms, check Admin Console > Limits for Devstral.
5. Groq: console.groq.com account, key, check Limits page Free Plan tab.
6. Local Ollama (recommended for experiments): install, pull a pinned model; no account needed.
7. Skip: Ollama Cloud, Cerebras (card/credits), GitHub Models (retired).

## 6. Unverified list
Ollama Cloud OpenAI-compat/free quota/context; Devstral on Experiment tier and its data terms; Mistral exact limits; tool-calling, structured-output, and context-window claims for Groq, Gemini, OpenRouter, OpenCode models; Groq free-plan numbers; Gemini free-tier limit table; OpenRouter free coding model list; "Others" in section 1.

## Live verification — OpenRouter (2026-11-21)

Measured, not from documentation.

- **Auth:** the browser sign-in cannot be used by the gateway; an API key is required (`TRACEFORGE_OPENROUTER_API_KEY` in git-ignored `.env`). The key's own limit reads `limit: 0`, `limit_remaining: 0`, `usage: 0`, `is_free_tier: true` (from `GET /api/v1/key`), so the key cannot spend money.
- **Catalog:** the public `GET /api/v1/models` listed 476 models, 11 ending in `:free`, all with `pricing.prompt = 0` and `completion = 0` and `tools` in `supported_parameters` (e.g. `nvidia/nemotron-3-ultra-550b-a55b:free`, `google/gemma-4-31b-it:free`, `inclusionai/ling-3.2-flash:free`). The list changes; recheck before pinning.
- **Smoke test** (`python -m traceforge.agent.smoke --provider openrouter --model nvidia/nemotron-3-ultra-550b-a55b:free --no-cache`): PASSED. Native `tool_calls` returned for `get_service_status({"service":"worker"})`; latency 5156 ms and 7281 ms for the two live calls. Account usage after the test: 0.
- **Free-only guard:** `--model openai/gpt-4o-mini` was refused before any request: `free_only: openrouter model id must end with ':free'`.
- **Not measured:** daily request cap (research says 50/day on `:free` models with <$10 credit — unverified here), data-use terms of this model's provider, coding quality (no benchmark run yet), determinism across repeated calls at temperature 0.
- **Decision (corrected 2026-11-21):** the intended primary cloud model is **Devstral**, not Nemotron. OpenRouter has no free Devstral (only `mistralai/devstral-2512`, paid: $0.4 in / $2 out per 1M tokens). Nemotron `:free` is kept only as an experimental alternative and connectivity check; local `qwen2.5-coder:7b` is the reproducible baseline. No paid model is used. Open: whether Mistral's free Experiment plan serves `devstral-small-latest` (check in the Mistral console; unverified).
- **Security note:** the key was pasted into the chat transcript instead of entered through the terminal. Treat it as exposed: revoke it at openrouter.ai/settings/keys and create a new one (limit 0) when convenient.

## Ollama Cloud — Devstral Small 2 (investigated 2026-11-21; NOT enabled)

Sources (fetched 2026-11-21): https://ollama.com/library/devstral-small-2 and `/tags`, https://ollama.com/zerocopia/devstral-small-2, https://ollama.com/pricing, https://docs.ollama.com/cloud/usage, https://docs.ollama.com/cloud/faq.

| Question | Finding |
|---|---|
| Does the exact model exist? | Yes, two entries: official `devstral-small-2:24b-cloud` (256K context, text+image, tools) and third-party `zerocopia/devstral-small-2:24b-cloud` (29 downloads, updated 6 months ago). The official one is the one to use if we use Ollama Cloud at all; the third-party namespace is unreviewed. |
| Free? | **Not guaranteed.** The pricing page lists "Pay as you go $0 — pay per token for every cloud model"; the included usage credits ($60 / $300 per month) belong to paid Pro/Max plans. Devstral is not in the published per-million-token price table. No free starter allowance is documented on the pages read. |
| Can usage trigger charges? | Cloud models are billed per token ("usage credits"); whether a zero-balance free account is simply refused or billed is **unverified**. Explicit credit purchase is a separate action we will not take. |
| Auth needed | `ollama signin` (browser, Ruhan) or an API key from ollama.com settings. |
| Safe non-billable check | With an API key, `GET https://ollama.com/api/balance` returns remaining included and purchased credits, and `GET /api/usage` returns request counts and cost. Ruhan can create the key (no payment) and tell Claude to query these two endpoints; no model request is needed. |
| Gateway compatibility | The existing `ollama` profile (`http://localhost:11434/v1`) would route a `-cloud` model through the local server after sign-in; tool calling is listed for the model but **not tested** (no request made). The `tool_calls_from_text` adapter already covers models that print calls as text. |
| What we did | Added a hard guard: any Ollama model tagged `-cloud`/`:cloud` is refused by the gateway unless `TRACEFORGE_LLM_ALLOW_OLLAMA_CLOUD=true` (default false). Before this the `ollama` provider was allowlisted wholesale, which would have let a cloud-tagged model through silently. |
| Local alternative | The same Devstral Small 2 is also available locally (`devstral-small-2:24b`, 15 GB, 384K context) but a 24B model on a 6 GB GPU with 16 GB RAM would be mostly CPU-offloaded; **not tested, not downloaded** (large download needs approval). |

Decision: see DECISIONS B12. Next step if Ruhan wants to pursue it: create an Ollama API key, then Claude runs only the balance/usage GET calls to see whether the account has any included credits.

### Update — measured account state (2026-11-21, read-only)
`GET https://ollama.com/api/balance`: included allowance **$0**, included balance **$0**, purchased **$0** (period 2026-10-26 → 2026-11-26). `GET /api/usage?range=30d`: 697 requests, 3,334,000 input / 20,717 output tokens, `usage_usd` 0.388 (pre-existing activity; billing status unknown). Conclusion: no free allowance on this account for cloud models, so `devstral-small-2:24b-cloud` cannot be used at a guaranteed $0. No model request was made. See DECISIONS B14.

### Re-investigation — Devstral on Ollama Cloud is retired (2026-11-21, read-only)
Trigger: a Reddit post (r/ollama, "ollama free tier model status", not readable without login) was reported to list `devstral-small-2:24b-cloud` and `devstral-2:123b-cloud` as available on free accounts.
- Official retirement list, https://docs.ollama.com/cloud/model-lifecycle: `devstral-2:123b` (alt `mistral-large-3:675b`) and `devstral-small-2:24b` (no alternative) retire on **July 15, 2026**, before today (2026-11-21).
- Live availability for this account, `GET https://ollama.com/api/tags` with Ruhan's key: 24 cloud models (beam, clef:27b, deepseek-v4-pro, deepseek-v4.1-flash, gemma4:31b, glm-5.2/5.3/5.3-flash, gpt-oss:120b/20b, inkling-2-small, kimi-k2.6/k2.7-code/k3/k3.1-pro, mimo-v2.6-flash/pro, minimax-m3/m3.1-flash, mistral-large-4, muse-spark-open, nemotron-3-super/ultra) — **no Devstral**.
- Pricing page FAQ: Pay-as-you-go accounts pay per request with usage credits; included credits are used first, then purchased balance; no free plan is described. Account balance: included $0 / purchased $0.
- Conclusion: the Reddit claim is outdated; the model cannot be reached. We made no request to it. See DECISIONS B14.
- Possible free alternatives among currently listed cloud models are billed (per-token prices on the pricing page) and have no confirmed free allowance, so they stay disabled by the gateway guard.
