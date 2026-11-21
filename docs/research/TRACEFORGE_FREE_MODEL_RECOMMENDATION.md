# TraceForge free-model recommendation (OpenRouter / OpenCode study, 2026-11-21) — awaiting Ruhan's approval

Nothing was changed: gateway, conditions, `.env` model settings and experiment definitions are untouched; no paid request, credit, payment method or paid fallback; no key printed. Sources: `FREE_CODING_LLM_PROVIDER_SURVEY.md` (live catalog/endpoints/limits), `CODING_LLM_BENCHMARK_COMPARISON.md`, `FREE_CODING_LLM_REDDIT_FINDINGS.md` (Reddit was not retrievable; public proxies only), earlier `CODING_LLM_COMPARISON.md`, `DEVSTRAL_OLLAMA_INVESTIGATION.md`.

## Headline answers
1. **Is any genuinely free model competitive with Claude Sonnet/Opus for complex software engineering? No** (evidence below). The best measured free-ish model sits about 25 points under Sonnet 5.5 on Terminal-Bench 4.1.
2. **Primary (recommended, provisional): `nvidia/nemotron-3-ultra-550b-a55b:free` on OpenRouter.** **Backup: local `qwen2.5-coder:7b`** (unlimited, verified, weaker). A cloud backup worth testing next: `baidu/ernie-5.5-flash-preview:free`.
3. **Route: OpenRouter, not OpenCode.** OpenCode's free models "require OpenCode" (cannot be called from our gateway) and its API route requires billing details and credits.
4. **Accessible at $0 today? Yes for the primary**: endpoint pricing is zero, our key has a $0 limit, and a live tool-call smoke test passed twice. **Quota today: 13 of 50 free requests remain** (resets 00:00 UTC).
5. **Biggest weaknesses:** limited free quota (50/day, 20/min) that cannot carry the full experiment; single vendor endpoint (no failover; "limited-time" rosters change); agent-loop reliability pattern ("benchmark-good, agent-loop-weak": retries, early stopping); no structured-output mode on this endpoint; privacy terms unverified.

## Shortlist (genuinely $0 endpoints reachable from our gateway)
| Rank | Model ID | Provider | Cost | Ctx / max out | Tools / struct. | Coding evidence (independent unless noted) | Community | Main weaknesses |
|---|---|---|---|---|---|---|---|---|
| 1 | nvidia/nemotron-3-ultra-550b-a55b:free | OpenRouter (Nvidia endpoint) | $0 | 1M / 65,536 | yes / no | SWE-bench Verified 69.0% (Vals, mini-SWE-agent), LiveCodeBench 85.98%; no Terminal-Bench/SWE-rebench; NVIDIA reports 70.7 (vendor) | CodeRabbit (vendor-adjacent): near parity in quality (58/105 vs 60/105) but 36.5 retries/run vs 0.3 and early stopping; OpenCode issues with array-vs-string tool args and idle timeouts | retries, hidden-reasoning token budget (handled), no JSON mode |
| 2 | baidu/ernie-5.5-flash-preview:free | OpenRouter (Baidu) | $0 | 1.02M / 921,600 | yes / yes | only a Baidu-reported 46.5 on Terminal-Bench 4.0 seen via aggregators (unverified); no independent score | none found | unmeasured; preview |
| 3 | google/gemma-4-31b-it:free | OpenRouter (Google AI Studio) | $0 | 262K / 32,768 | yes / yes | no SWE scores found | local reports slow runs, 66.7–98.2% swings (snippets) | endpoint uptime 93%; Google free tier may use data; output cap 32K |
| 4 | nvidia/nemotron-3.5-lightning:free | OpenRouter (Nvidia, nvfp4) | $0 | 1M / 65,536 | yes / no | none found | "trial use only" | quantised; unmeasured |
| 5 | particle-ai/particle-1:free | OpenRouter (Particle AI) | $0 | 1.05M / 131,072 | yes / yes | none found | none | unmeasured |
| 6 | recursive/flint-v1.0:free, inclusionai/ling-3.2-flash:free | OpenRouter | $0 | 262K–1M | yes / yes | none found | none | unmeasured |
| – | nvidia/nemotron-3.5-super-vl:free | OpenRouter | $0 | 1M / 131,072 | yes / yes | **Terminal-Bench 0.3% (mini-swe-agent)** | ranks 64–67/68 on Arena agent index | very poor agentic score: exclude |
| – | openrouter/free | OpenRouter router | $0 | 200K | yes / yes | n/a | random model per request by design | **unsuitable**: model changes between calls |
| base | qwen2.5-coder:7b (local) | Ollama | $0 | 4K default (16K variant) | text-parsed / – | no current independent score; our probes: 7/10 exact fixes, slow | – | weak at multi-line edits; slow on 6 GB GPU |
Not available at $0 through an API we can use: DeepSeek V4.1 Flash (free only inside OpenCode), Inkling (small / 2-small / 2-mini, paid on OpenRouter), Qwen 3.8 27B (paid), Devstral (retired), Ollama Cloud models (allowance $0).

## Is the leader close to Claude? (comparable independent numbers only)
- Terminal-Bench 4.1, Claude Code harness: Sonnet 5.5 63.9%, Opus 5.5 / Fable 5.2 65.8%, Haiku 5.5 40.0%; best free-ish: DeepSeek V4.1 Flash 38.5% (OpenCode-only). Nemotron models score lower or are unmeasured; Nemotron 3.5 Super VL 0.3% under mini-swe-agent (different harness).
- Arena agent/code index (2026-11-18): Fable 5.2 1,489; Opus 5.5 1,373; Sonnet 5.5 1,329; DeepSeek V4.1 Flash 1,128; Nemotron 3.5 Super VL / Inkling ranks 64–67 of 68.
- SWE-bench Verified (saturated/contaminated): Nemotron 3 Ultra 69.0% vs 95–97% for older Claude versions.
- A cheap paid Claude tier (Haiku 5.5, 40.0%) matches the best measured free-ish model.
No benchmark here measures abstention, evidence grounding or minimal patches.

## Are OpenRouter free endpoints reliable enough for TraceForge experiments?
- **Volume: no.** 50 requests/day cannot carry ~1,700 runs; even the 4 seed cases × 4 conditions × 3 attempts exceed a day.
- **Reproducibility: partly.** A fixed `:free` ID is stable per call and cached by our gateway, but rosters/limits change without notice, single-vendor endpoints have no failover, the router is random, and reports include silent 404s/429s. No report of an undisclosed weight swap behind a fixed ID was found.
- Conclusion: usable for **pilots, spot checks and a small dev set spread over days**; not for the full 2×2×3 experiment.

## If the $0 rule were relaxed (information only, no action taken)
OpenRouter lists DeepSeek V4.1 Flash at about $0.05 in / $0.20 out per 1M tokens. With the planning assumption of ~43M input and ~5M output tokens for the full experiment, that would be roughly **$3** (the `-1017` variant at $0.15/$0.60 ≈ $10): a rough estimate from assumed token counts, not a quote, and it also has the strongest independent agentic score among cheap models (Terminal-Bench 38.5%). This is your decision; the budget stays $0 and nothing was enabled.

## Smoke-test results so far (partial; SMOKE TEST, not a benchmark)
Fixed 8-task harness `spikes/free_model_smoke/` (tasks are my own synthetic design; hidden checks never shown to the model; real pipeline prompts/tools/edit policy; temperature 0; K=1). **Nemotron 3 Ultra `:free`, 3 of 8 tasks completed before the 12-request cap** (results and raw replies: `spikes/free_model_smoke/results/openrouter__nvidia_nemotron-3-ultra-550b-a55b_free/`):
| Task | Truth | Result |
|---|---|---|
| cfg_direct_pool_size | configuration | correct class + target, grounded; patch applied, policy ok, 2-line diff, **hidden check passed** |
| abstain_bare_500 | insufficient_evidence | **correctly abstained** (4 requests, 30 s) |
| abstain_misleading_warning | insufficient_evidence | **wrong: confidently diagnosed a configuration cause** from a misleading stale warning (and proposed a patch) — the failure TraceForge's abstention design is meant to prevent |
Schema compliance 3/3, invalid tool calls 0, truncation 0. Tokens in/out 15,189 / 3,896 over the 12 live requests. n=3 single runs: one wrong abstention is a warning sign, not a rate. Remaining 5 tasks (including the prompt-injection task and the cross-file fix) wait for the next quota reset; local Qwen and the other candidates are not yet run.

## What is still to test (not yet run)
- Fixed 8-task smoke set (`spikes/free_model_smoke/`) on local Qwen, Nemotron 3 Ultra, ERNIE 5.5 Flash Preview, Gemma 4 31B: root cause, evidence grounding, abstention, patch minimality, schema compliance, repeatability. Cloud runs need quota (about 30–60 requests per model); local Qwen has no limit. Results will be labelled smoke tests, not benchmarks, and appended here.
- Privacy/retention terms per free endpoint (unverified).

## Confidence
Free-route conclusion (OpenRouter over OpenCode): high (official pages). Primary choice: medium (best-documented of the free options, but weak on agent-loop reliability and no independent agentic score). Rankings below #2: low (no data). "No free model matches Claude": medium-high.

## Approval needed
Say whether to adopt Nemotron 3 Ultra `:free` as the TraceForge primary with local Qwen as backup (or choose otherwise). Until then nothing is changed.
