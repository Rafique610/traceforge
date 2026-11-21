# Free coding LLMs for agent workflows: published developer experience (research as of 2026-11-21)

Method: WebSearch + WebFetch on public pages only. No repo reading, no model/API calls, no billable requests.

## 1. Reddit status: NOT RETRIEVABLE

- The WebSearch tool rejected `reddit.com` outright ("domains are not accessible to our user agent"). No Reddit thread could be searched or fetched. No workaround was attempted (no mirrors, proxies, archives, alternative front-ends).
- No Reddit thread is cited as a primary source here. Three secondhand mentions of Reddit threads are noted below. They were relayed by other pages, which I read, and I did not see the threads themselves.
- Net effect: Reddit-specific sentiment (r/LocalLLaMA, r/opencode, r/openclaw, r/ChatGPTCoding) is a gap in this report, not a finding.

## 2. Source ledger

Read = full page fetched, but WebFetch summarises through a small model, so quotes are as returned. Snippet = search-result summary only. FH = first-hand. Dates marked "year n/a" are not shown on the page.

| # | Source | Platform | Date | Type | Coverage | Summary / short quote |
|---|---|---|---|---|---|---|
| 1 | https://opencode.ai/docs/zen | Vendor docs | Live page (fetched 2026-11-21) | Vendor, authoritative for terms | Read | Every free model is "for a limited time". Per-model retention and region lists in section 4. |
| 2 | https://explainx.ai/blog/opencode-deepseek-v4-1-flash-free-zen-go-limits-what-is-verified-2026 | Blog | Facts as of 2026-10-15 | Secondary, explicitly separates verified from unverified | Read | No end date published. Same-weights/quantization/limits parity with the paid endpoint is undocumented. The 200K cap is claimed only by a secondary write-up. A GitHub issue reports an earlier free DeepSeek model vanishing after promo. Also mentions a Console breach affecting linked provider keys (not independently checked). |
| 3 | https://github.com/anomalyco/opencode/issues/28141 | GitHub issue | Opened 2026-05-18, closed 2026-10-05 | FH user reports | Read | Big Pickle returns `AI_APICallError` while other free models work. No maintainer reply. Later commenters report "Internal Server Error" through v1.18.12. Closed "not planned" by the stale bot. |
| 4 | https://github.com/anomalyco/opencode/issues/33714 | GitHub issue | 2026-06-24, closed 2026-10-01 | FH | Read | Nemotron 3 Ultra Free on Zen: "Upstream idle timeout exceeded" during long generations and tool calls, then "write failed". Suspected slow tokens/sec. Closed stale, not planned. |
| 5 | https://github.com/anomalyco/opencode/issues/36354 | GitHub issue | 2026-07-11, auto-closed 2026-09-10, new report 2026-09-22 | FH | Read | Tool calls fail with "Internal server error" and endless retries on deepseek-v4-flash/pro and mimo-v2.5-pro (Zen and Go). Suspected missing `reasoning_content` echo. A follow-up says `mimo-v2.6-flash-free` returns 500 when the Read tool returns a PDF. Workaround: convert PDF to PNG or text. Not fixed. |
| 6 | https://forums.developer.nvidia.com/t/nemotron-ultra-failure-to-write-a-file-in-opencode/375163 | Vendor forum | 2026-07-01; reply 2026-09-29 | FH | Read | Nemotron Ultra passes arrays/objects where OpenCode's write tool needs a string for multiline JS/TS. The user's workaround was a "writing-files" skill. A second user (Ollama + Zed) reports "failed file writes not infrequently". No official fix. |
| 7 | https://coderabbit.ai/blog/nemotron-3-ultra-release | Vendor blog | 2026-06-04 | First-hand benchmark, but not independent (sells a review product, internal dataset) | Read | 105-problem internal code-review benchmark. Ultra passed 58/105 vs baseline 60/105, so near parity. Ultra averaged 36.5 retries per run vs 0.3. "The model sometimes voluntarily stops before producing the required output marker". No tool-call metrics. Latency 7:06 vs 8:31, but cost was higher. |
| 8 | https://developer.nvidia.com/blog/nvidia-nemotron-3-ultra-powers-faster-more-efficient-reasoning-for-long-running-agents/ and related NVIDIA blogs | Vendor | 2026 (exact date n/a) | Promotional | Snippet only | Claims consistent tool use across harnesses. Terminal-Bench 2.0 about 54% in NVIDIA's own table, behind GLM 5.1 (64%) and Kimi K2.6 (67%) as reported by the search summary. I did not read the table myself. |
| 9 | https://openrouter.ai/docs/api/reference/limits | Vendor docs | Live | Authoritative | Read | Free models: 20 req/min. Daily: 50 req if under 10 credits ever purchased, 1000 if at least 10 (threshold text has an unfilled placeholder on the page). Docs don't say whether failed attempts count. A negative balance can break free models. |
| 10 | https://openrouter.ai/docs/guides/routing/routers/free-models-router | Vendor docs | Live | Authoritative | Read | `openrouter/free` picks a random free model after filtering for needed capabilities (tools, images, structured outputs). The `model` field shows what ran. "Availability changes often." Latency may rise at peak. Best for prototyping, low volume. |
| 11 | https://dev.to/josh_green_dev/free-llms-on-openrouter-keep-going-404-i-fixed-it-with-120-lines-of-python-43i1 | DEV | Mar 8 (year n/a, likely 2026) | FH (self-reported) | Read | 3 of 6 hardcoded free models returned 404 "model not found", 1 returned 429. The pipeline failed silently for about a week. "Free model availability is a moving target." |
| 12 | https://dev.to/aicostdev/i-burned-through-openrouters-free-models-faster-than-i-expected-lessons-from-hitting-the-limits-4iai | DEV | Jul 30 (year n/a) | FH, but promotional (pushes RouteAI) | Read | Rate limits arrived sooner than expected, one hit mid-demo, intermittent availability. No models named. "Free routes are rate-limited more aggressively than paid ones". |
| 13 | https://dev.to/lars_winstand/i-got-excited-about-free-nemotron-and-kimi-too-then-my-247-agent-started-falling-apart-1418 | DEV | Jun 8 (year n/a, likely 2026) | Mostly secondhand (cites Reddit r/openclaw and a Reddit thread on OpenRouter), promotional (Standard Compute) | Read | Relayed Reddit error: "all models are temporarily rate limited. Please try again in a few minutes." Argues that retries and parallel tool fan-out turn burst throttling into outages. Own incident details thin. |
| 14 | https://dev.to/lkp/i-used-gemma-4-as-a-local-coding-agent-with-opencode-heres-what-happened-19mh | DEV | May 13/19 (year n/a) | FH, not promotional (contest entry) | Read | Gemma 4 **26B A4B** (not 31B) run locally in OpenCode. Good at repo understanding and Playwright-assisted debugging. Output "a little bit inconsistent for UI and have many bugs"; "Gemma 4 did not replace me as a developer." No explicit tool-call errors. |
| 15 | https://martinfowler.com/articles/exploring-gen-ai/local-models-for-coding-experiences.html | Blog | n/a | FH | Snippet only | Gemma 4 31B and Qwen3.6 35B: long reasoning chains and very slow edits. Small default context in runtimes can explain much of this. |
| 16 | https://www.epam.com/insights/ai/blogs/qwen-vs-gemma-local-llm-coding-agent-test | Vendor blog | n/a | FH benchmark by a consultancy | Snippet only (fetch got 403) | Gemma 4 31B in the pi harness on a 15k-LOC Flutter app: scores swung 66.7-98.2% across runs, failed one task three times. Not verified beyond the snippet. |
| 17 | https://forum.level1techs.com/t/open-source-models-for-coding/251758 | Forum | n/a | FH anecdotes | Snippet only | One user finds Gemma 4 / Qwen 3.6 underwhelming. Another runs Qwen 35B in Cline on a large Ruby repo and says it works well. |
| 18 | Hacker News: https://news.ycombinator.com/item?id=50239488, ?id=49600944, ?id=50168634 | HN | n/a | FH comments | Snippet only | Thin. One claims GLM + a DeepSeek advisor via omp "feels Opus 4.6 level" (paid or open models via OpenRouter, not free tier). One says OpenCode doesn't quantize its models (Dax, per a commenter). I could not tell which comment sits in which thread. Not read in full. |
| 19 | https://opencode.ai/data/compare/... (MiMo-V2.6-Flash and LongCat pages) | Vendor aggregator | n/a | Vendor benchmark-style scores | Snippet only | MiMo-V2.6-Flash tool-use score 68/100, coding 62/100. LongCat 2.5 Preview has no coding data. Not agent-loop evidence. |
| 20 | https://github.com/zed-industries/zed/issues/49933 | GitHub | n/a | FH | Snippet only | Concerns an unexpected `openrouter/auto` request. Not about free routing. Marginal relevance. |

Not retrieved or not found (do not assume content): any Reddit thread; any aider, Cline or Roo Code issue about these specific free models (I did not search those trackers directly, so "not found" means "not searched"); any HN thread dedicated to free-tier reliability; the Medium/Towards AI articles in the results (paywalled or not opened).

## 3. Per-candidate evidence (what I found)

| Model | Evidence found | Quality of evidence |
|---|---|---|
| Nemotron 3 Ultra | Sources 4, 6, 7, 8 above. Write-tool argument-type errors, idle timeouts, a high retry rate, quality near a baseline in code review. | Best-covered. Several FH reports, though the benchmark is vendor-adjacent. |
| Nemotron 3.5 Lightning, 3.5 Super VL | Only in OpenCode docs: free, logged, "Trial use only — do not submit personal or confidential data." | No hands-on reports found. |
| ERNIE 5.5 Flash Preview, Particle-1, Ling 3.2 Flash, Inkling Small, Qwen 3.8 27B | Nothing relevant found. | Not found. |
| Inkling 2 Small | Only OpenCode docs: retained and may be used for monitoring/training, with a long region exclusion list. | No hands-on reports found. |
| Flint (Recursive) | Only OpenCode docs ("Flint 40B Free"): may be used for improvement, 30-day retention. | No hands-on reports found. The "(Recursive)" naming was not verified. |
| Gemma 4 31B | Sources 15 and 16 (local runs, slow, variable) plus source 14 (the 26B variant). | A few FH reports, all local. Not tied to a free hosted endpoint. |
| DeepSeek V4.1 Flash (OpenCode free) | Docs plus the explainx write-up. Related DeepSeek V4 tool-call failures in issue 36354 (paid variants). | Terms are documented. No free-tier agent-loop quality report found. |
| MiMo-V2.6-Flash | Issue 36354 follow-up (500 on PDF Read), aggregator scores. | One FH bug. |
| Beam, LongCat 2.5, Big Pickle | Docs only for Beam and LongCat 2.5. Big Pickle has issue 28141. | Big Pickle: outage reports. Others: no hands-on reports found. |

## 4. Synthesis

**Repeated consensus (3+ independent sources)**
1. Free tiers are for prototyping, not sustained agent loops: OpenRouter docs, sources 11, 12, 13. All agree that availability, limits and the roster change without notice.
2. Hardcoding a single free model ID eventually breaks. Sources 11, 12 and the OpenRouter docs agree. Fallback chains and live catalog checks are the common fix.
3. Failures cluster around agent plumbing (tool-call arguments, reasoning-content round-trips, timeouts) more than raw code ability. Sources 4, 5, 6 and 7 show this.

**Isolated or weakly supported opinions**
- The "Opus-level" HN claim (paid, not free-tier).
- Gemma 4 "best local" or "underwhelming" (conflicting single anecdotes).
- The 200K context cap on free DeepSeek V4.1 Flash (one secondary source).
- Any claim that a free model is "as good as paid" (promotional blog titles in the search results, not read).

**Good on benchmarks, weak in agent loops.** Nemotron 3 Ultra is the clearest case: near-baseline code-review accuracy, but an average of 36.5 retries per run and early stopping (source 7), write-tool type errors (6) and idle timeouts (4). It also trails GLM 5.1 and Kimi K2.6 on Terminal-Bench per NVIDIA's own table (snippet only). The Gemma 4 reports show strong repo understanding but long reasoning chains and slow, inconsistent edits.

**Tool-call failure patterns seen**
- Wrong argument types (array/object where a string is expected) in the write tool (6).
- Provider-side 400/500 errors that the client shows as "Internal server error" and retries endlessly, tied to `reasoning_content` handling (5).
- Idle timeouts mid-tool-call on slow models, leaving later tool calls failing (4).
- Structured-output termination before the required marker (7).
- Multimodal tool results (PDF Read) crashing a free endpoint (5).

**Patch quality.** There is little direct multi-file patch evidence. The best data points are the Gemma 26B build-and-debug run, which found a path mismatch and fixed it but left bugs, and the CodeRabbit near-parity result for review. I found no systematic multi-file patch evaluation of any candidate on a free endpoint.

**OpenRouter free reliability**
- Documented: 20 req/min; 50/day, or 1000/day after $10 credits; "availability changes often"; latency may rise at peak (9, 10).
- Reported: 404 "model not found" on 3 of 6 models and silent pipeline failure (11); mid-demo rate limiting (12); "all models are temporarily rate limited" (13, secondhand from Reddit).
- A search summary lists several guides with conflicting limit numbers (20/200, 20/50). The official page is the authority.
- `openrouter/free` picks a random model per request by design, so behavior and tool-call quality can vary between turns of one session. This is documented, not a silent change. The `model` field in the response shows what ran. I found no report of an undisclosed swap behind a fixed model ID.
- I did not find a GitHub issue specific to `openrouter/free` in agent loops.

**OpenCode free-tier caveats (from the docs, source 1)**
- Every free model is "for a limited time", with no end dates. Source 2 reports an earlier free DeepSeek model disappearing after promo.
- Retention varies per model:
  - Zero retention and no training: DeepSeek V4.1 Flash, LongCat 2.5 (hosted in China, 100 requests/day), Hy4 flash.
  - May train, or retained for improvement: Big Pickle, Iceman, Inkling 2 Small, Flint 40B (30 days).
  - No training, 30-day safety retention: Beam.
  - Logged, trial use only, no confidential data: the Nemotron 3.5 models.
  - Unspecified: MiMo-V2.6-Flash, Jev 1.13.
- Region restrictions:
  - Inkling 2 Small: EU, Iceland, Liechtenstein, Norway, Cuba, Iran, North Korea, Russia, Ukraine, Venezuela.
  - Beam: a long list including China, Russia, Iran, Nigeria and others.
  - Others: none listed.
- Stability: Big Pickle outage with no maintainer response (3); the Nemotron timeout and MiMo/DeepSeek 500s were closed by the stale bot without a fix (4, 5). Bot auto-closure after 60 days means closed does not mean fixed.

## 5. Confidence and limitations

- Overall confidence: medium on the OpenRouter and OpenCode policy and limits facts (official docs, read directly). Medium-low on model quality conclusions. Low on the candidates with no evidence (ERNIE 5.5 Flash Preview, Particle-1, Ling 3.2 Flash, Inkling Small, Qwen 3.8 27B, Nemotron 3.5 variants, Beam, Flint, LongCat 2.5, Big Pickle quality).
- Reddit was entirely inaccessible, and the HN, Fowler, EPAM and Level1Techs items are snippets only.
- WebFetch output is summarised by a small model, so quotes could be imperfect. Verify before citing externally.
- Many dev.to posts lack a year. I inferred 2026 only where flagged "likely".
- Several write-ups are promotional (NVIDIA, CodeRabbit, RouteAI, Standard Compute).
- Docs and limits change often. The OpenCode page and explainx figures are dated 2026-10-15 to 2026-11-21 and should be re-checked.
- The "Flint (Recursive)" name and several candidate names matched OpenCode docs only partially. I did not confirm identities beyond those docs.
