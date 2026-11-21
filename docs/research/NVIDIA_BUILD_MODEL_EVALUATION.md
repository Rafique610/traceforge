# NVIDIA Build (build.nvidia.com) as a free coding-model route for TraceForge (2026-11-21)

Scope: read-only research on public pages and the public model list. No account was created, no key entered, no inference endpoint called, nothing billable. WebFetch summarises pages with a small model, so each quote is only as reliable as that summary; the API Trial Terms PDF was downloaded and read directly (text extracted locally). "Unverified" means no official page stated it. Nothing here suggests bypassing any restriction.

## 1. Bottom line

1. A free mechanism exists and is permanent in principle: an account plus an API key on build.nvidia.com starts a "trial" with no time limit, no credits and no card mentioned (NVIDIA forum staff answers, Sept 2025). The only published limit is about 40 requests/minute per account, and per-model limits are explicitly unpublished.
2. **The blocker for this user is Pakistan phone verification.** Phone verification is required before a key is issued. Over a dozen forum threads from May to Sept 2026 report that Pakistan (+92) is missing from the country dropdown and the "Send Code" button stays disabled. None shows an official fix. Whether a Pakistani user can get a key today is **unverified and looks unlikely via self-service**. The only official route is emailing help@build.nvidia.com for manual verification, with no evidence of success.
3. If access is obtained, the best primary is **moonshotai/kimi-k3.1-pro** (strongest independent evidence of the candidates: Terminal-Bench 4.1 59.7% under Claude Code vs Sonnet 5.5 63.9%). Backup: **z-ai/glm-5.3-flash** (37.0% TB 4.1 Claude Code). Both are conditional on the endpoint being usable on the trial tier, which no official page confirms per model.
4. Privacy is the second major constraint. The API Trial Terms (v. Sept 19, 2025) section 3.3(iv) says NVIDIA collects User Content and Generated Content "to improve NVIDIA products and services, including AI models", which conflicts with the staff forum statement that content is used "solely to provide" the service. Send only synthetic or public fixtures, never private code.

## 2. Free access mechanism (with sources)

| Question | Finding | Source / date |
|---|---|---|
| How to get free access | Create an account and API key on build.nvidia.com; this starts trial use, "no extra steps required". Trial "is not limited by a time period". "Trial" means "prototyping, research, development, testing, learning, etc." | NVIDIA forum staff (sophwats), thread "Request More (+4,000 credits)", 17 Sept 2025 |
| Developer Program | The docs page says Developer Program members have free access to NIM API endpoints for prototyping; "for prototyping, research, development and testing purposes only"; production needs an AI Enterprise license (from $4,500/GPU/yr). Whether a build.nvidia.com key requires separately joining the Program is unverified; staff say account + key is enough. | https://docs.api.nvidia.com/nim/docs/product (fetched 2026-11-21) |
| Credits | Staff: "We no longer use a credit-based system for build.nvidia.com ... replaced by rate limits for trial usage" (10 Sept 2025). But the Terms text (section 1.4, v. Sept 19, 2025) still allows credits, limited-time trials and "limited number of API access instances", so NVIDIA reserves the right to change this. Earlier community figures of 1,000 credits are obsolete or unverified. | forum thread above; Terms PDF |
| Credit card / billing | Nothing on any page fetched requires a card; Terms section 3.5 mentions "payment method (if any)". Not required per the forum answers, but no official signup page was readable. Treat as probably not required, unverified. | forum; Terms |
| Phone verification | Required (many forum threads, including users stuck at "exceeded limits", SMS not arriving). Pinned staff-style post: email help@build.nvidia.com with registered email, phone numbers tried, error details. | https://forums.developer.nvidia.com/ (several threads, Apr-Sept 2026) |
| Pakistan | See section 2a. | |
| Permanent? | Terms 1.2/1.3: NVIDIA "will be under no obligation to deliver any future API Service" and may terminate pre-release services at any time. Free in practice, not guaranteed. | Terms PDF |

### 2a. Pakistan specifics

- 28 Jun 2026 "Cannot verify phone, country not in dropdown" (poster is in Pakistan, +92 missing): the only reply says account access issues are not handled on the forum and points to the pinned post (help@build.nvidia.com). https://forums.developer.nvidia.com/t/cannot-verify-phone-country-not-in-dropdown/374813
- 3 Jul 2026 and 21 Aug 2026 threads: no staff reply, no resolution shown. A search returned roughly 18 other Pakistan (+92) threads (titles such as "Phone verification not available for Pakistan (+92) - blocks API key generation", "Manual Account Verification Request - Pakistan (+92)"). Skipping the step blocks key creation.
- No official supported-country list, no export-control statement naming Pakistan, and no confirmed resolution was found. Pakistan is not under a general US embargo, so this looks like an SMS-provider/coverage gap rather than a legal block, but that is an inference and **unverified**. Terms 15.4 requires compliance with US export and sanctions law ("restrictions on destinations, end-users and end-use").
- Do not use virtual numbers, borrowed foreign numbers, VPNs or burner SIMs to get around this. It likely violates the terms (a forum thread notes verification is strict because of bot-farm abuse) and could get the account banned.
- Legitimate option: email help@build.nvidia.com (see actions). Success rate unknown.

## 3. Rate limits

- Published: about 40 RPM per account. Evidence is community statements plus staff acknowledging it: "the team is aware of the implications of the 40 rpm rate limit" (MarkusHoHo, 13 May 2026). No official docs page states it. The account UI reportedly shows your maximum rate limit (staff, 10 Sept 2025).
- Per-model: "The rate limits vary for each model, and we do not publish those" (staff, 10 Sept 2025). Staff also say limits depend on model, use case and overall traffic, and "there is no official way ... to receive a rate limit increase on that same tier" (29 Apr 2026). Increase requests on the forum may be treated as spam.
- Daily caps: none documented; **unverified**. Hot new models reportedly get congested (429s, bot farms; thread dated 20 Apr 2026).
- Can it carry experiments? 40 RPM is about 57,600 requests/day if never throttled, far more than OpenRouter's 50/day, so request volume is plausible for the ~1,700-run plan, but per-model limits, 429s under load and an unpublished daily/abuse policy are unknown. Run a short pilot (small request count) and measure before committing. Agent loops use many calls per run; budget about 4-12 calls per run.

## 4. Terms (API Trial Terms of Service, v. September 19, 2025; read in full)

URL: https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf (the model pages say the trial service is governed by these terms).

- 1.2: access "for limited trial purposes only and without use of the API Service or Generated Content in production". 1.4: without a Subscription, use only "for internal testing and evaluation purposes, not in production". Research is a named trial purpose in staff answers, so a university research evaluation of TraceForge fits; a public service or a product built on it does not.
- 4.2: you may not "copy, sell, rent, sublicense, transfer or distribute or make available to others any portion of the API Service or Generated Content" except as 1.2 allows. Publishing model outputs in a paper or releasing a dataset of generated patches may be affected: unresolved; ask the supervisor or NVIDIA before publishing generated content. A forum user asking this (8 Oct 2026) got no answer beyond "use help system / counsel".
- 2.3: NVIDIA will not store or use content after the session "unless expressly disclosed". 3.3: NVIDIA collects, without identifying users, session metrics, logs, feedback and "(iv) User Content and Generated Content to improve NVIDIA products and services, including AI models", and logs use for security/abuse and shares with third-party providers. 2.7: NVIDIA may monitor and review content. So treat prompts as potentially retained and used for training. Conflict with staff statement (June 2025) means: assume the stricter reading.
- 2.6(a): do not submit confidential information, personal data or sensitive data. TraceForge fixtures must therefore be synthetic or public.
- 1.3: pre-release services may be withdrawn at any time. Section 14: binding arbitration. Adult of legal age only.
- Per-model licences (model cards): Nemotron 3 Ultra and 3.5 Lightning, OpenMDW 1.1, "ready for commercial and non-commercial use"; Kimi K3.1 Pro, NVIDIA Open Model Agreement and Kimi K3.1 Pro License; MiniMax M3.1 Flash, NVIDIA Software and Model Evaluation License and "for research and development only"; Mistral Large 4, ready for commercial or non-commercial use. These govern weights, not the hosted trial.

## 5. OpenAI-compatible API details

- Base URL `https://integrate.api.nvidia.com/v1`, `POST /v1/chat/completions`, `Authorization: Bearer <key>` (docs.api.nvidia.com llm-apis page and kimi API reference). An HTTP 202 can be returned with polling at `GET /v1/status/{requestId}`; an OpenAI-SDK gateway must handle this (kimi reference). Key prefix `nvapi-` is community convention, unverified here.
- Per-model request schemas differ and use `additionalProperties: false` (unlisted fields may be rejected):

| Field | kimi-k3.1-pro (API ref) | nemotron-3-ultra (API ref) |
|---|---|---|
| model | `moonshotai/kimi-k3.1-pro` | `nvidia/nemotron-3-ultra-550b-a55b` |
| max_tokens | 1-65,536, default 16,384 | 1-32,768, default 16,384 (our OpenRouter smoke used 65,536) |
| stream default | true | true |
| tools | yes (OpenAI-style) | not in schema; model card says function calling supported |
| response_format | not listed | not listed; model card: structured output NOT supported |
| stop | not listed | yes (string or array) |
| reasoning | `reasoning_effort` low/high/max, default low | `reasoning_effort` none/medium/high, default high (maps to chat_template_kwargs enable_thinking) |
| temperature | not listed | 0 < t <= 1, default 1 (so temperature 0 is not allowed) |
| seed | yes | yes |

  Note the nemotron reference rejecting `temperature: 0` conflicts with TraceForge's temperature-0 policy; unverified whether an invalid value errors or is clamped.
- Structured output on NIM generally goes through `extra_body={"nvext": {"guided_json": schema}}` (NVIDIA NIM LLM docs, self-hosted); whether the hosted trial endpoint accepts it or OpenAI-style `response_format` is **unverified per model**. TraceForge already uses tool calls and its own schema validation, so this is not blocking.
- Reasoning output field name (`reasoning_content` vs inline) is unverified for hosted models; the gateway must tolerate null or missing fields and larger token use from hidden reasoning (same lesson as the OpenRouter Nemotron run).
- Compatibility with an OpenAI-SDK gateway: likely, via base_url override. Gaps to test: 202 polling, rejected unknown params, no `temperature=0`, `max_tokens` caps, stream-by-default behaviour, tool-call argument formats.

## 6. Candidate table

"Free eligibility": **confirmed free** requires an official page naming that endpoint as free. None does; every model card says only "The trial service is governed by the NVIDIA API Trial Terms of Service", which means trial (non-production, rate-limited), not an explicit free label. So every row is **unverified (trial tier, probably usable at $0 if a key is obtained)**. The catalog listing is not proof. Per-model limits: unpublished for all.

Benchmarks: TB = Terminal-Bench 4.1 (independent, tbench.ai, Claude Code harness, "max"). Vals = SWE-bench Verified (independent, saturated). All numbers from `_benchmarks_raw.md` / `CODING_LLM_BENCHMARK_COMPARISON.md`; Sonnet 5.5 = TB 63.9%, Opus 5.5 = 65.8%, Haiku 5.5 = 40.0%.

| Exact ID | Free eligibility | Context (card) | Tools / structured | Benchmark evidence | Privacy / licence | Gateway notes |
|---|---|---|---|---|---|---|
| moonshotai/kimi-k3.1-pro | unverified; trial terms | 1,048,576; max output undisclosed (API max_tokens 65,536) | yes / yes (card) | **TB 59.7% (+-4.2)** independent, 2026-10-24; Vals not found. Closest to Sonnet 5.5 (-4.2 pts, within about 1 CI) | trial terms 3.3(iv); NVIDIA Open Model Agreement | tools yes; no response_format or stop in schema; reasoning_effort low/high/max |
| z-ai/glm-5.3-flash | unverified; its model page returned 404 under the tried slugs, so card unread | not verified | not verified | TB 37.0% (+-3.6); Vals 92.0% (independent, saturated) | same trial terms | no API ref read |
| minimaxai/minimax-m3.1-flash | unverified; card says "for research and development only" | conflicting: 262,144 vs "up to 1M" | yes / yes | not found on any independent benchmark (m3: TB 7.6% mini-swe-agent, Vals 75.0%) | Evaluation License + MiniMax Community License | API ref 404 |
| nvidia/nemotron-3-ultra-550b-a55b | unverified; trial terms | 1,048,576 | yes / **no** | Vals 69.0%, LCB 85.98% (independent); TB not found; vendor 70.7 Verified. Our OpenRouter smoke: 1 of 2 abstention tasks wrong | OpenMDW; trial terms | max_tokens cap 32,768, no temp 0, same model as the OpenRouter free route |
| mistralai/mistral-large-4-1t-a52b | unverified; trial terms | conflicting 262,144 vs 1M | yes / yes | TB 27.6% (+-3.9); Vals not found | trial terms; Mistral licence for MaaS | reasoning low/medium/high; max_completion_tokens includes reasoning |
| nvidia/nemotron-3.5-lightning-30b-a3b | unverified; trial terms | 1,048,576 | yes / yes | Vals 52.8% only | OpenMDW | cheap/fast, weak |
| nvidia/nemotron-3.5-super-vl-120b-a12b | unverified | not read | not read | TB 0.3% (mini-swe-agent); Arena rank 64 of 68 | | exclude |
| bigcode/starcoder2-15b | unverified | 16K-class (not verified) | text completion model, no tools expected | none current | | not agentic; exclude |
| google/gemma-4-31b-it, poolside/laguna-xs-2.1, others in the 33-model catalog | unverified | not read | not read | gemma: none; laguna: not in benchmarks files | | not evaluated |

Vendor-reported figures (Nemotron 3 Ultra 70.7 Verified, 89.0 LCB v6, TB 2.1 56.4) are NVIDIA's own and are not comparable with the independent numbers. TB 4.1 rows for Kimi/GLM/Mistral use the Claude Code harness like the Claude rows, so they are the fair comparison. Benchmarks do not measure abstention, grounding or patch minimality.

## 7. Recommendation (conditional on a working key)

- **Primary: moonshotai/kimi-k3.1-pro.** Best independent agentic score of any candidate (59.7% vs Sonnet 5.5 63.9%, same harness), tools and structured output supported by the card, 1M context. Note this is much better than the OpenRouter free primary (Nemotron 3 Ultra, no TB score). Risks: hot model, likely congested or tightly limited; per-model rate limit unpublished; privacy as above.
- **Backup: z-ai/glm-5.3-flash** (TB 37.0%, Vals 92.0% independent), cheaper and probably less contended; card unverified. If its card shows no tool support, fall back to nemotron-3-ultra (known tool-call behaviour from our smoke test) or mistral-large-4.
- Compared with what we have: local qwen2.5-coder:7b has no current benchmark and 7/10 exact fixes in our probes, so any candidate above is a likely quality gain but with weaker control (rate limits, logging) than local. OpenRouter Nemotron 3 Ultra `:free` is the existing cloud option (50 requests/day, tools yes, structured output no; smoke 3/8 tasks, one overconfident misdiagnosis). NVIDIA Build would replace the daily request ceiling (if a key is obtainable) and add stronger models, at the cost of the Pakistan verification risk, data-use terms and unpublished limits.
- Keep local Qwen as the guaranteed fallback. Do not run the full experiment on NVIDIA's trial tier until a pilot confirms limits and a supervisor accepts the terms (4.2 publication clause, 3.3 data use).

## 8. Actions for the user (do not paste any key into chat)

1. Read the API Trial Terms (link in section 4) and decide with the supervisor whether the research use, outputs publication (4.2) and data use (3.3(iv)) are acceptable. Use only synthetic/public code.
2. Create an NVIDIA account at https://build.nvidia.com/ with a university email (optionally join the NVIDIA Developer Program, whether needed is unverified).
3. Try the in-site phone verification with your own real Pakistani number. If +92 is missing or no SMS arrives, stop and email help@build.nvidia.com (registered email, the number you tried, the error text or screenshot, a one-line statement of the research use). Do not use someone else's number, a virtual number or a VPN. Do not post your number on the forum.
4. If verification succeeds, open a model page, choose "Get API Key"/"Build with this NIM", generate a key, and check the rate limit shown in your account (top right).
5. Put the key only in the local, git-ignored `.env`, for example (variable names are suggestions; match whatever the gateway reads):
   `NVIDIA_API_KEY=` (paste value locally)
   `NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1`
   `NVIDIA_MODEL=moonshotai/kimi-k3.1-pro`
   Never commit it, never send it to chat; rotate it if it leaks.
6. Tell the project agent only "key set" and the rate limit you see. Then a short capped pilot (about 20-40 requests) can check: model ID accepted, tool calls, 202 polling, temperature handling, reasoning field, 429 behaviour, and whether glm-5.3-flash and kimi respond. Stop at the first billing prompt: no card is needed, and any prompt for payment means stop.
7. If no key can be obtained, keep OpenRouter Nemotron 3 Ultra `:free` plus local Qwen; nothing is lost.

## 9. Unverified or open items

Per-model "free" labelling; per-model and daily limits; whether any country list exists; whether a card is ever required; hosted `response_format`/`guided_json` support; glm-5.3-flash and kimi card details beyond kimi's page (glm pages returned 404; build.nvidia.com FAQ was 404); effect of the data-use clause; Pakistan verification outcome. Forum "related topic" dates are activity dates and unreliable; staff attribution of "MarkusHoHo" and "sophwats" is inferred from "we/our team" wording and thread context, not a page label.

## Sources
- https://integrate.api.nvidia.com/v1/models (public, 33 models, fetched 2026-11-21)
- https://docs.api.nvidia.com/nim/docs/product ; https://docs.api.nvidia.com/nim/reference/llm-apis
- https://build.nvidia.com/moonshotai/kimi-k3_1-pro and /apireference ; https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b (+ /apireference); https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b ; https://build.nvidia.com/minimaxai/minimax-m3.1-flash ; https://build.nvidia.com/mistralai/mistral-large-4-1t-a52b
- NVIDIA API Trial Terms of Service v. September 19, 2025 (PDF link in section 4)
- Forum: https://forums.developer.nvidia.com/t/request-more-4-000-credits-option-on-build-nvidia-com/344567 ; /t/clarification-on-trial-api-use/334275 ; /t/api-rate-limit-increase-is-not-granted-by-requesting-it-here/368420 ; /t/is-nim-free/369368 ; /t/bot-farms-are-ruining-build-nvidia-com-please-save-this-platform-some-practical-fixes/367242 ; /t/cannot-verify-phone-country-not-in-dropdown/374813 ; /t/phone-verification-not-available-for-pakistan-92-blocks-api-key-generation/380926 ; /t/unable-to-verify-phone-number-from-pakistan-for-nvidia-build-api-access/375470 ; /t/api-trial/385386
- Local: docs/research/CODING_LLM_BENCHMARK_COMPARISON.md, docs/research/_benchmarks_raw.md, docs/research/TRACEFORGE_FREE_MODEL_RECOMMENDATION.md

## Confidence
Free mechanism and terms: medium-high (staff quotes and full Terms text). Pakistan blocker: medium (many consistent reports, no official statement). Per-model free status and limits: low (unpublished). Model ranking: medium (one independent version-matched benchmark; no TraceForge-specific eval).
