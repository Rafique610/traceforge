# Coding LLM comparison for TraceForge (research of 2026-11-21)

Status: research only. No configuration, gateway or experiment file was changed; no billable request was made; no credits purchased. Companion files: `REDDIT_CODING_MODEL_CONSENSUS.md` (community findings), `_benchmarks_raw.md` (every benchmark number with source), `TRACEFORGE_MODEL_RECOMMENDATION.md` (the decision).

## 1. What was verified about the account (read-only, 2026-11-21)
| Check | Result | Source / method |
|---|---|---|
| Models served to this account | 24 cloud models (list below) | `GET https://ollama.com/api/tags` with Ruhan's key |
| Capabilities + context | each model's `capabilities` and `context_length` from `POST /api/show` (metadata only, not inference) | saved at `D:\AI\ollama_account_models.json` |
| Allowance | included $0, included balance $0, purchased $0 (period 2026-10-26 → 2026-11-26) | `GET /api/balance` |
| Prior usage | 697 requests, $0.388, all on 2026-10-26 (a one-off day) | `GET /api/usage?range=30d` |
| Pricing model | every cloud model is billed per token; "Pay as you go accounts pay for each request with usage credits"; included credits are used first, then purchased balance; no Free plan is listed | https://ollama.com/pricing (fetched 2026-11-21) |
| Devstral | `devstral-2:123b` and `devstral-small-2:24b` retired 2026-07-15; not in the account catalog | https://docs.ollama.com/cloud/model-lifecycle ; `/api/tags` |
| Qwen3-Coder | not in the account catalog (only on the retirement list) | `/api/tags` ; lifecycle page |

**Is any Ollama Cloud model confirmed free for this account? No.** The account has no allowance and the official pricing page describes no free plan. Third-party sources (dev.to, forums, 2026 articles; see the community file) describe a Free tier metered by GPU time with 5-hour and 7-day windows where heavy models (e.g. Kimi, GLM) return 403 without Pro and small ones (e.g. gpt-oss:20b) work. Those claims are undated/old, conflict with the official page, and could not be tested without risking a billable request, so they are **unverified**. Whether a request at a $0 balance is refused or billed is also **unknown**.

## 2. Candidate table (Ollama Cloud models on the account)
Prices are per 1M tokens (input / output) from the Ollama pricing page; "Free?" is *not confirmed* for every row. Benchmarks: see section 3 for versions and caveats; "nf" = not found. Community = low-confidence Hacker News/dev-blog evidence only (no Reddit access).

| Model (exact ID) | Ctx | Tools | $ in / out | Confirmed free? | Independent coding evidence | Community | TraceForge note |
|---|---|---|---|---|---|---|---|
| kimi-k3.1-pro | 1M | yes | 2.00 / 10.00 | no | Terminal-Bench 4.1 59.7% (best open entry, Claude Code harness) | none found | strongest agentic open model on the account; most expensive |
| kimi-k3 | 1M | yes | 3.00 / 15.00 | no | TB 23.0%; Vals SWE-bench Verified 93.4% | none | worse than k3.1-pro on TB despite price |
| kimi-k2.7-code | 262K | yes | 0.95 / 4.00 | no | Verified 78.2%; LCB 82.05% | none | code-specialised; old-ish |
| kimi-k2.6 | 262K | yes | 0.95 / 4.00 | no | Verified 76.2%; LCB 86.77% | HN: several "daily driver / good value"; also slow, verbose, loops, breaks heredoc edits | |
| glm-5.2 | 1M | yes | 1.40 / 4.40 | no | **SWE-rebench 62.9% (highest open, next to top closed)**; Verified 82.8%; LCB 69.5% | praised for planning/long reads/debugging (blogs/HN), occasional bad runs | best independent evidence for real issue fixing |
| glm-5.3 | 1M | yes | 1.40 / 4.40 | no | Verified 95.4%; TB 41.2%; Arena agent-code 1,104 (rank 35/65) | none | |
| glm-5.3-flash | 1M | yes | 0.15 / 0.50 | no | Verified 92.0%; TB 37.0%; Arena 1,059 | none | cheap |
| deepseek-v4-pro:0813 | 1M | yes | 1.32 / 3.96 | no | Verified 96.4% but SWE-rebench 40.2% and **TB 6.7%** | "closest to Opus" in listicles; weak on one niche API | scores disagree strongly: Verified saturated |
| deepseek-v4.1-flash | 1M | yes | 0.30 / 1.20 (off-peak 0.15 / 0.60) | no | TB 38.5%; Arena agent-code 1,128 (conflicting 1,133) | none | best price/performance on TB among cheap models |
| minimax-m3 | 512K | yes | 0.60 / 2.40 | no | SWE-rebench 47.2%; Verified 75.0%; **TB 7.6%**; LCB 82.15% | none | |
| minimax-m3.1-flash | 1M | yes | 0.15 / 0.60 | no | Arena 1,087 | none | |
| gpt-oss:120b | 131K | yes | 0.15 / 0.60 | no | Verified 33.6%; SWE-bench Pro 16.2%; LCB 83.2% | tool-calling depends on serving stack (harmony leaks, parallel-call bugs) | cheap but weak at repo tasks |
| gpt-oss:20b | 131K | yes | 0.07 / 0.30 | no (sources claim light models are free — unverified) | LCB 80.4% only | | likely the only candidate to be usable on a free tier |
| nemotron-3-ultra | 262K | yes | 0.10 / 3.00 | no | Verified 69.0%; LCB 85.98% | none | same family as OpenRouter `:free` model we tested |
| nemotron-3-super | 262K | yes | 0.015 / 0.60 | no | nf (Nemotron 3.5 variants are different) | none | |
| gemma4:31b | 262K | yes | 0.14 / 0.40 | no | nf | none | |
| mistral-large-4 | 1M | yes | 0.70 / 2.10 | no | TB 27.6% | none | |
| mimo-v2.6-pro / flash | 1M | yes | 0.435 / 0.87 ; 0.14 / 0.28 | no | TB 27.0% / 16.1% | none | |
| muse-spark-open | 1M | yes | 1.25 / 4.25 | no | SWE-bench Pro 55–61.5% (version ambiguous) | none | |
| inkling-2-small, beam, clef:27b | 1M / 1M / 64K | yes / yes / no tools | 0.30/1.00 ; 0.125/0.40 ; 0.24 | no | nf | none | clef has no tool capability (`decision`,`vision`) |

Structured outputs: Ollama's `capabilities` list shows no explicit "structured output" flag; docs say structured outputs are not supported for cloud models (research agent finding, to be re-verified). TraceForge does not require them: its gateway uses tool calls and parses SEARCH/REPLACE text.

## 3. Benchmarks used and what they mean for TraceForge
Details and per-model numbers: `_benchmarks_raw.md`. Rules followed: no cross-benchmark averaging; versions stated; vendor-reported scores excluded.
| Benchmark (version/date) | Measures | Relevance | Caveat |
|---|---|---|---|
| SWE-rebench (window 2026-05-15→07-01) | resolving fresh real GitHub issues, contamination-controlled | **best proxy** for diagnose-and-patch | few candidates scored |
| SWE-bench Pro public (Scale) | harder multi-file issue fixing | good | very few candidates scored |
| Terminal-Bench 4.1 | agentic shell tasks | tool-use/long-horizon | measures shell agency, not patch minimality |
| SWE-bench Verified (Vals.ai snapshot 2026-09-01, mini-SWE-agent) | issue fixing, 500 tasks | low: saturated, contaminated (deepseek-v4-pro 96.4% yet 40.2% on rebench) | official swebench.com rows did not render |
| LiveCodeBench (Vals snapshot) | competitive-programming code generation | low for debugging | |
| Aider Polyglot (last update 2025-11-20) | edit-format code editing | stale; nothing for current candidates | |
| Arena Agent/Code index (2026-11-18) | human/preference-based | weak | some numbers snippet-only |
No benchmark measures abstention, evidence use or patch minimality. TraceForge's own evaluation is the only direct test.

## 4. Rankings
### A. Best coding models overall, regardless of price (independent evidence only)
1. Closed frontier models (Claude Fable 5.2 / Opus 5.5: Terminal-Bench 65.8%, Arena coding index top 2); not on Ollama.
2. Among open models: **glm-5.2** (SWE-rebench 62.9%), **kimi-k3.1-pro** (TB 59.7%), glm-5.3 (TB 41.2%, Verified 95.4%), deepseek-v4.1-flash (TB 38.5%), minimax-m3 (SWE-rebench 47.2% but TB 7.6%).
Confidence: medium for numbers; medium-low for completeness.

### B. Best models available through this Ollama account for $0
**None can be confirmed.** The account has no allowance and no free plan is documented. If a Free tier exists as third parties say, the only plausible free-eligible candidates are small ones (gpt-oss:20b and maybe gpt-oss:120b) — unverified and weak on repo-level tasks (SWE-bench Pro 16.2% for 120b). The strongest *verified-$0* options are elsewhere: OpenRouter `:free` models (tool calling verified for `nvidia/nemotron-3-ultra-550b-a55b:free`) and local `qwen2.5-coder:7b`.

### C. Best for TraceForge (diagnosis, minimal patch, tool-schema reliability, abstention), regardless of price
glm-5.2 > kimi-k3.1-pro > glm-5.3 ≈ deepseek-v4.1-flash > kimi-k2.6 > nemotron-3-ultra > minimax-m3 (rebench but poor TB) > gpt-oss:120b. Basis: SWE-rebench/Terminal-Bench evidence; community reports are thin. Within $0-verified options: nemotron-3-ultra:free (cloud) > qwen2.5-coder:7b (local).

## 5. Compatibility with the existing gateway (code inspection + prior live tests, no new calls)
- The gateway speaks the OpenAI chat-completions format with tools, temperature 0, seed, replicate-aware cache, retries, a free-only guard. Ollama Cloud models can be called through the local Ollama server after `ollama signin`; `-cloud` models are currently refused by the guard (`llm_allow_ollama_cloud` false).
- Reasoning models spend output tokens on hidden reasoning; the gateway default was raised to 4096 and truncation is reported (`output_truncated`).
- Models that print tool calls as JSON text are handled (`tool_calls_from_text`).
- Live-verified compatible: `nvidia/nemotron-3-ultra-550b-a55b:free` (OpenRouter; native tool calls) and local `qwen2.5-coder:7b`. All 24 Ollama Cloud models report `tools` except `clef:27b`, but none was called.

## 6. Cost context (planning estimate, not a measurement; budget remains $0)
Assumption (to be replaced by measured token counts): about 1,700 runs for the full 2×2×3 experiment on ~144 cases, ~25K input + ~3K output tokens per run → ~43M input and ~5M output tokens. Rough list-price totals: gpt-oss:120b ≈ $9, deepseek-v4.1-flash ≈ $13 (off-peak ≈ $7), glm-5.3-flash ≈ $9, glm-5.2 ≈ $82, kimi-k3.1-pro ≈ $136. Free OpenRouter models are limited to a few dozen requests per day (documented limit, not re-measured), which cannot cover this volume.

## 7. Limitations and confidence
- **No Reddit data** could be retrieved (search filter 400 error, fetch blocked); community conclusions rest on Hacker News, dev blogs and forums, mostly pre-dating the current model generation. Confidence: low.
- Benchmark pages were summarised by a small model; spot-check key numbers before citing them in the paper. Confidence: medium.
- Free-tier eligibility is **unverified for every Ollama Cloud model**.
- No model was evaluated on TraceForge tasks except Nemotron `:free` and local Qwen (small, partial tests recorded in `limits-report.md`).
