# Coding LLM benchmark comparison: free models vs Claude Sonnet/Opus (2026-11-21)

Question: is any genuinely free model competitive with Claude Sonnet / Opus for complex software engineering?

Short answer: **No free model has a comparable, independent score that comes close to Claude Sonnet 5.5 or Opus 5.5 on a hard agentic benchmark. The best free candidate with independent data (Nemotron 3 Ultra) is only measured on saturated or non-comparable benchmarks. On the one benchmark with several free models and Claude on the same version and harness family (Terminal-Bench 4.1), the best free-tier model is far behind.**

Method and rules: pages fetched with WebFetch/WebSearch on 2026-11-21 (WebFetch summarises pages with a small model, so each row is only as reliable as that summary). Only numbers on the same benchmark version and similar scaffold are compared. "not found" means not on the page or the page did not render; nothing is estimated. Vendor and aggregator numbers are in separate tables. Earlier verified numbers are from `_benchmarks_raw.md` (same-day retrieval) and are marked "(raw)". No billable or model calls were made.

## 0. Model names and versions (verified)

- Claude names on the Arena Agent/Code Index (Nov 18) and Terminal-Bench 4.1: **Claude Fable 5.2**, **Fable 5.1**, **Opus 5.5**, **Sonnet 5.5**, **Haiku 5.5**. Sonnet 5.5 released 2026-09-28 (Anthropic page), Opus 5.5 2026-09-22, Haiku 5.5 2026-10-07 (leaderboard date; its launch is a second-hand search summary).
- Free candidates: names are as given by the requester. Verified on benchmark pages only where noted. Inkling Small 2 and Inkling Small appear on Terminal-Bench 4.1. "Nemotron 3.5 Super VL" is a different model from nemotron-3-ultra-550b-a55b and from nemotron-3.5-lightning.
- Free-tier status itself was not re-verified here (given by requester).

## 1. Terminal-Bench 4.1 (independent, https://www.tbench.ai/leaderboard, fetched 2026-11-21)

Agentic shell tasks, pass/fail by tests, 95% CI. The agent harness differs by row: Claude rows use Claude Code (max effort); open free-tier rows use mini-swe-agent (effort "none" or xhigh). That is a scaffold mismatch, so the gap partly reflects harness and effort. DeepSeek V4.1 Flash is the only non-Claude row also run with Claude Code, which makes it the one fair comparison.

| Model (as listed) | Agent | Rate | Date | Free? |
|---|---|---|---|---|
| Fable 5.2 (max) | Claude Code | 65.8% (2.8) | 2026-11-09 | no |
| Opus 5.5 (max) | Claude Code | 65.8% (3.1) | 2026-09-22 | no |
| Sonnet 5.5 (max) | Claude Code | 63.9% (3.0) | 2026-09-28 | no |
| Haiku 5.5 (max) | Claude Code | 40.0% (3.6) | 2026-10-07 | no |
| DeepSeek V4.1 Flash 1017 (max) | Claude Code | 38.5% (3.8) | 2026-10-17 | free on OpenCode only; cheap paid elsewhere |
| Qwen3.8-Max-0902 (max) | Claude Code | 27.0% (3.9) | 2026-09-02 | no (Max, not 27B) |
| MiMo V2.6 Pro (none) | mini-swe-agent | 27.0% (3.6) | 2026-09-22 | no |
| MiMo V2.6 Flash (none) | mini-swe-agent | 16.1% (3.4) | 2026-09-22 | free on OpenCode |
| Inkling Small 2 (xhigh) | mini-swe-agent | 13.0% (2.8) | 2026-11-05 | named inkling-2-small; free on OpenCode |
| Inkling Small (none) | mini-swe-agent | 0.9% (0.9) | 2026-07-30 | no |
| Nemotron 3.5 Super VL (none) | mini-swe-agent | 0.3% (0.6) | 2026-10-15 | free (OpenRouter) |

Not on the page: Nemotron 3 Ultra, Nemotron 3.5 Lightning, Gemma 4, ERNIE 5.5 Flash, Ling 3.2 Flash, Particle, Flint, LongCat, beam, big-pickle, iceman, Qwen3.8 27B, qwen2.5-coder-7b.

Reading: Sonnet 5.5 beats the best free-ish entry (DeepSeek V4.1 Flash, same Claude Code harness) by about 25 points; the CIs are about +-4, so this is a clear gap. Free entries under mini-swe-agent are 0-27 points below, but the harness confound means they would likely do better under Claude Code (unknown). Even Haiku 5.5, Anthropic's cheapest model, scores 40.0%, about equal to DeepSeek V4.1 Flash.

## 2. SWE-bench Verified (saturated, contaminated: floor check only)

SWE-bench Verified has been public since 2024, top scores are 95-97% and Vals archived it as saturated. Use it only to exclude weak models.

### 2a. Independent: Vals.ai, Mini-SWE-agent harness, snapshot 2026-09-01 (raw)
| Model | Score |
|---|---|
| Claude Opus 5 | 97.00% |
| Claude Fable 5 | 95.00% |
| Qwen 3.8 27B (not free) | 86.00% |
| deepseek-v4-flash 0731 (not 4.1) | 88.80% |
| nemotron-3-ultra | 69.00% |
| Nemotron 3.5 Lightning | 52.80% |
| not found | Sonnet 5.5, Opus 5.5, Fable 5.2, Haiku 5.5 (newer than archive), Gemma 4 31B/26B, ERNIE, Ling, MiMo V2.6 Flash, Inkling, qwen2.5-coder-7b |

Caution: the Vals snapshot lists Opus 5 and Fable 5, not Opus 5.5 / Fable 5.2 / Sonnet 5.5. Same harness, but not the same Claude version.

### 2b. Vendor-reported, NVIDIA model card (https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16)
NVIDIA reports Nemotron 3 Ultra 550B-A55B at 70.7 SWE-bench Verified (other NVIDIA pages show 71.9/69.7 and a blog range of 65-70.4% across Pi, OpenHands, Hermes, OpenCode and Mini SWE Agent). Harness not mapped on the card. The independent Vals figure (69.0%) is consistent with the vendor figure. Same card: Terminal Bench 2.1 56.4 (a different version from 4.1, not comparable), LiveCodeBench v6 89.0, and open comparison models (Kimi-K2.6 75.7, GLM-5.1 76.2, DS-v4-Pro 74.5) on NVIDIA's own runs.

Anthropic's Sonnet 5.5 page (https://www.anthropic.com/claude-sonnet-5-5) has no SWE-bench Verified or Pro figure. Not found for Sonnet 5.5, Opus 5.5, Fable 5.2 on Verified.

## 3. SWE-bench Pro public (Scale AI, independent operator)

https://labs.scale.com/leaderboard/swe_bench_pro_public, fetched 2026-11-21. 25 rows, stale. Newest Claude rows: claude-opus-4-6 (thinking, mini-swe-agent) 51.90; claude-opus-4-5-20251101 45.89; claude-4-5-Sonnet 43.60; claude-4-5-haiku 39.45. Closest open rows: qwen3-coder-480b 38.70; gemma-3-27b-it 11.38. **No Sonnet 5.5 / Opus 5.5 / Fable 5.2 / Haiku 5.5 and no candidate free model appears. Not found.** (Gemma 3, not Gemma 4.) Not usable for the question.

## 4. SWE-rebench (independent, fresh issues)

https://swe-rebench.com, window 2026-05-15 to 2026-07-01, 111 tasks / 65 repos, model rows are scaffold-unspecified on the page (re-fetched 2026-11-21, consistent with raw).

| Model | Resolved % +-SE (Pass@5) | Cost/problem |
|---|---|---|
| Fable 5 [high] | 64.5 +-1.41 (78.4) | $4.40 |
| Opus 5 [high] | 63.4 +-1.35 (74.8) | $3.47 |
| GLM-5.2 [high] (not free on named lists) | 62.9 +-1.19 (81.1) | $1.40 |
| Sonnet 5 [high] | 56.8 +-0.94 (74.8) | $1.43 |
| MiMo V2.5 Pro (not V2.6 Flash) | 46.5 +-0.54 (65.8) | $0.10 |
| Gemma 4 31B | N/A (listed, no result) | |
| Nemotron, DeepSeek V4.1 Flash, Inkling, Qwen3.8, Haiku 5.5, Sonnet 5.5, Opus 5.5, Fable 5.2 | not found | |

Takeaway: the window predates Sonnet 5.5 / Opus 5.5 / Fable 5.2 and all named free candidates. A non-free open model (GLM-5.2) matches Opus 5 here, which shows open models can reach Claude level on fresh issues, but it is not on the free list and was not tested against the 5.5 generation.

## 5. Aider Polyglot

Page last updated 2025-11-20 (raw); nothing for any 2026 model, so **not found for all candidates and for the 5.x Claude models**. Do not use.

## 6. LiveCodeBench

- Vals (independent, archived 2026-09-01, raw): nemotron-3-ultra 85.98%; Claude Fable 5.1 90.52%, Fable 5 89.78%, Opus 5 89.03%. Version/window not stated; near-saturated (top ~20 within 4 points); contamination likely.
- Vendor: Gemma 4 31B 80.0% and 26B A4B 77.1% LiveCodeBench v6 (Google model card, per search summary); Nemotron 3 Ultra 89.0 v6 (NVIDIA card). Vendor numbers are v6, Vals' version is unstated, so Vals and vendor are not comparable with each other.
- Reading: free models are within roughly 4-10 points of Claude on competitive programming, so this is where they look closest. It is the weakest proxy for repo-level engineering.

## 7. Arena Agent/Code Coding Index (https://arena.ai/leaderboard/agent/code, 2026-11-18; 1,031,799 sessions, 68 models)

Preference/usage-based Elo-like index, not hidden tests.

| Model | Index | Rank |
|---|---|---|
| Claude Fable 5.2 (Max) | 1,489 | 1 |
| Claude Opus 5.5 (Max) | 1,373 | 2 |
| Claude Sonnet 5.5 (Max) | 1,329 | 4 |
| Claude Opus 5.5 (High) | 1,315 | 6 |
| Claude Sonnet 5.5 (High) | 1,238 | 13 |
| DeepSeek V4.1 Flash 20261017 (Max) | 1,128 (raw: a snippet said 1,133, conflicting) | n/a on fetch |
| Inkling | no index | 65 |
| Inkling-Small | no index | 67 |
| Nemotron 3.5 Super VL 120B (NVFP4) | no index | 64 |
| Nemotron 3 Ultra, MiMo v2.6 Pro/Flash, Qwen3.8 (Max/Flash Next/27B), Haiku 5.5 (High) | on chart, no score or rank read | |

Sonnet 5.5 (Max) leads DeepSeek V4.1 Flash by about 200 Elo-like points. The free OpenCode models (MiMo Flash, Inkling Small) and Nemotron sit at the bottom of the ranked list. Not found: Gemma 4, ERNIE, Ling, LongCat, Particle, Flint.

## 6b. Vendor-reported / aggregator figures (separate, not comparable)

- Anthropic (vendor): Sonnet 5.5 Terminal-Bench **4.0** 70.6%, Opus 5.5 66.4% (Opus at xhigh); FrontierCode 1.1 Sonnet 5.5 46.2% (Max) / 52.1% (Xhigh, inferred by fetch tool), Opus 5.5 54.4%; CursorBench 4.0 Sonnet 5.5 55.5%, Opus 5.5 57.8%. Page gives no scaffold, says full method is in the system card. Terminal-Bench 4.0 is not 4.1; a search summary says Artificial Analysis got 63.6% vs 59.6% (Sonnet vs Opus), conflicting with Anthropic's ordering gap. No SWE-bench numbers on this page.
- Baidu via aggregators (orcarouter, llm-stats; unverified): ERNIE 5.5 Flash Preview Terminal-Bench **4.0** 46.5; DeepSWE v1.1 71.2 vs DeepSeek-V4.1-Flash-1017 77.0. Aggregators say the Baidu numbers mix harnesses and judge models. Code Arena ~1668 not statistically clear. If 46.5 on Terminal-Bench 4.0 were reproduced independently it would be notable (Sonnet 5.5 vendor 70.6 on the same 4.0 version, a 24-point gap), but it is vendor-reported only.
- Haiku 5.5 APEX-SWE 55.1% Pass@1: from a LinkedIn post via search summary; not verified.
- NVIDIA Nemotron 3 Ultra: see 2b.
- Gemma 4 31B: no SWE-bench or Terminal-Bench found in model cards or search summaries (only LiveCodeBench v6 80.0, Codeforces ELO 2150, tau2-bench retail 86.4).
- ling-3.2-flash, particle-1, flint-v1.0, flint-40b, longcat-2.5, big-pickle, iceman, beam, nemotron-3.5-lightning (beyond Vals 52.8), qwen3.8-27b (beyond Vals 86.0): no usable coding scores found.

## 8. Summary table: free candidates vs Claude (same-benchmark, same-version only)

| Benchmark (version) | Claude Sonnet 5.5 | Claude Opus 5.5 / Fable 5.2 | Best free candidate with a score | Comparable? |
|---|---|---|---|---|
| Terminal-Bench 4.1 (independent) | 63.9% (Claude Code) | 65.8% / 65.8% | DeepSeek V4.1 Flash 38.5% (Claude Code, free only on OpenCode); free OpenRouter: Nemotron 3.5 Super VL 0.3%; OpenCode: MiMo Flash 16.1%, Inkling Small 2 13.0% (mini-swe-agent) | Yes for DS Flash; free rest has harness mismatch |
| Terminal-Bench 4.0 (vendor) | 70.6% | 66.4% | ERNIE 5.5 Flash Preview 46.5 (Baidu, aggregator) | Same version, both vendor-reported, different harnesses |
| SWE-bench Verified (Vals, Mini-SWE-agent) | not found | Opus 5 97.0 / Fable 5 95.0 (older gen.) | Nemotron 3 Ultra 69.0; Nemotron 3.5 Lightning 52.8 | Same harness, but Claude version older; saturated |
| SWE-bench Pro | not found | not found (Opus 4.6 51.9 old) | not found | no |
| SWE-rebench | not found (Sonnet 5 56.8) | Opus 5 63.4 / Fable 5 64.5 (older gen.) | none of the free candidates; Gemma 4 31B N/A | no |
| Aider Polyglot | not found | not found | not found | no |
| LiveCodeBench | not found (Fable 5.1 90.5) | Opus 5 89.0 | Nemotron 3 Ultra 86.0 (Vals); Gemma 4 31B 80.0 (vendor v6) | Vals-only comparable |
| Arena Agent/Code | 1,329 (Max) | 1,373 / 1,489 | DeepSeek V4.1 Flash 1,128; Inkling/Inkling-Small/Nemotron 3.5 Super VL ranks 64-67 | Yes (one index) |

## 9. Verdict (plain language)

- **Gap size.** On the only independent, version-matched agentic comparison (Terminal-Bench 4.1), Sonnet 5.5 and Opus 5.5 are at 64-66%, and the best free-model entry is about 38% (DeepSeek V4.1 Flash, only free on OpenCode, same harness) or 13-16% for the OpenCode free models run with mini-swe-agent. That is roughly a 25-50 point gap. On the Arena agent index Sonnet 5.5 is about 200 points above DeepSeek V4.1 Flash and the free Nemotron / Inkling models rank 64-67 of 68.
- **Where free models are close.** Competitive-programming-style tests: Nemotron 3 Ultra LiveCodeBench 86.0 (Vals) vs Opus 5 89.0; Gemma 4 31B 80.0. SWE-bench Verified is saturated; Nemotron 3 Ultra at 69% is about 25-28 points below Opus 5 / Fable 5 on the same harness but not far from other open models. A non-free open model (GLM-5.2) matches Opus 5 on SWE-rebench, so open models do reach Claude level in principle, just not in the free tier we found.
- **Where far.** Long-horizon agentic work (Terminal-Bench 4.1, Arena agent index), where the free models score either low or unmeasured.
- **Is any genuinely free model competitive with Sonnet/Opus?** Not on the evidence found. The only plausible contender, Nemotron 3 Ultra (vendor Terminal-Bench 2.1 56.4 and Verified 70.7), has no independent agentic number on a current benchmark, and its sibling Nemotron 3.5 Super VL scored 0.3%. ERNIE 5.5 Flash Preview's vendor-reported 46.5 on Terminal-Bench 4.0 is the one unverified lead worth checking independently. Many candidates (Ling, Particle, Flint, LongCat, beam, big-pickle, iceman, Gemma 4 on SWE tasks) have no coding benchmark data at all.
- **Local baseline.** qwen2.5-coder-7b: not found on any benchmark above (a 7B model from 2024). Qwen2.5-Coder-32B scored 16.4% on Aider Polyglot in 2024 (raw), so the 7B is expected to be well below that, but that is inference, not data. It is far below every candidate here.
- **Haiku 5.5 as a reference.** Haiku 5.5 (Terminal-Bench 4.1 40.0%) roughly equals the best free-ish agentic entry. A cheap paid Claude tier is therefore a stronger baseline than any free model with a measured score.

## 10. What these benchmarks cannot tell us for TraceForge

None of the above measure: abstention (saying "insufficient evidence" instead of guessing), evidence grounding (citing real trace/log lines), minimal-patch discipline (smallest correct diff), or behaviour under TraceForge's own prompts and schemas. Pass/fail on hidden tests rewards solving, not declining. Verified/Aider/LCB are contaminated or saturated. Harness differences (Claude Code vs mini-swe-agent) confound model comparisons. Free-tier routers (openrouter/free) change the underlying model, so no stable benchmark applies. Free endpoints may also have rate limits, quantisation (e.g. NVFP4) and logging terms that differ from the benchmarked configuration. TraceForge-specific evals are needed before choosing any free model.

## 11. Confidence

- Claude (Sonnet/Opus/Fable 5.x) clearly ahead of every free candidate on agentic tasks: **medium-high** (one independent version-matched benchmark plus the Arena index, both pointing the same way; harness confound for most free rows).
- Nemotron 3 Ultra roughly 25 points below older Claude on Verified: **medium** (Vals plus vendor agree, but Claude version mismatch).
- Statements about candidates with no data: **low**, deliberately left as "not found".
- Fetched pages were summarised by a small model and some leaderboards render with JavaScript, so a few rows may be missing; the SWE-bench Pro and Aider pages are stale. Recheck any figure before citing externally.

## Sources
- https://www.tbench.ai/leaderboard
- https://swe-rebench.com
- https://labs.scale.com/leaderboard/swe_bench_pro_public
- https://arena.ai/leaderboard/agent/code
- https://www.vals.ai/benchmarks/swebench and https://vals.ai/benchmarks/lcb (via `_benchmarks_raw.md`)
- https://www.anthropic.com/claude-sonnet-5-5 (vendor)
- https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16 (vendor)
- https://huggingface.co/google/gemma-4-31B and https://deepmind.google/models/gemma/gemma-4/ (vendor, via search summary)
- https://www.orcarouter.ai/blog/ernie-5-5-flash-preview-launch-post-benchmarks and https://llm-stats.com (aggregators, unverified)
- https://aider.chat/docs/leaderboards/ (via raw, stale)
