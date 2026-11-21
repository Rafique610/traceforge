# Raw benchmark evidence for coding LLMs (retrieved 2026-11-21)

Method: pages fetched with WebFetch/WebSearch on 2026-11-21. WebFetch summarises pages with a small model, so each row is only as good as that summary. Every number below was read from a fetched page. Nothing is estimated. "not found" means the model was not on the page or the page did not render. Rule: do not compare numbers across different benchmarks, versions or scaffolds. Within a table, compare rows only if the scaffold column matches.

Independent = run by the leaderboard operator or a third party. Vendor = lab-reported. No vendor model cards were retrieved, so no vendor-reported numbers are included; every table row below is leaderboard/third-party. Aggregator figures from search snippets are listed only in section 9 as excluded.

Candidates: glm-5.2, glm-5.3, glm-5.3-flash, kimi-k2.6, kimi-k2.7-code, kimi-k3, kimi-k3.1-pro, minimax-m3, minimax-m3.1-flash, deepseek-v4-pro, deepseek-v4.1-flash, gpt-oss-120b, gpt-oss-20b, nemotron-3-ultra, nemotron-3-super, gemma-4-31b, mistral-large-4, mimo-v2.6, muse-spark, devstral-2, devstral-small-2, qwen3-coder (30B, 480B, next), qwen2.5-coder-7b.

---
## 1. Terminal-Bench 4.1 (https://www.tbench.ai/leaderboard) - agentic shell tasks
- Measures: resolution rate on terminal tasks (agent has a shell; task tests decide pass/fail). Tasks are listed on the Harbor hub; the page gives no task count. Page carries an anti-training-corpus canary GUID. 95% CI shown.
- Version 4.1. Snapshot fetched 2026-11-21; newest entry 2026-11-18.
- Scaffold varies per row (Claude Code, Codex, Antigravity CLI, Muse Code, mini-swe-agent). Model and harness are confounded; only compare rows with the same agent. The page marks open-model families with an asterisk but does not explain it.
- Relevance for TraceForge: moderate. Tests tool calling and iterative shell work with pass/fail checks, close to a hidden-test verification loop. Does not test minimal patches, retrieval or abstention.
- Contamination: public tasks; canary only.

| Model | Agent | Rate (95% CI) | Date |
|---|---|---|---|
| kimi-k3.1-pro (max) | Claude Code | 59.7% (4.2) | 2026-10-24 |
| kimi-k3 (max) | Claude Code | 23.0% (3.7) | 2026-07-16 |
| glm-5.3 (max) | Claude Code | 41.2% (3.3) | 2026-08-14 |
| glm-5.3-flash (max) | Claude Code | 37.0% (3.6) | 2026-08-26 |
| glm-5.2 | not found | | |
| deepseek-v4.1-flash 1017 (max) | Claude Code | 38.5% (3.8) | 2026-10-17 |
| deepseek-v4-pro 0813 (max) | Claude Code | 6.7% (2.5) | 2026-08-13 |
| mistral-large-4 (max) | Claude Code | 27.6% (3.9) | 2026-10-06 |
| mimo-v2.6-pro (none) | mini-swe-agent | 27.0% (3.6) | 2026-09-22 |
| mimo-v2.6-flash (none) | mini-swe-agent | 16.1% (3.4) | 2026-09-22 |
| minimax-m3 (none) | mini-swe-agent | 7.6% (2.8) | 2026-06-01 |
| Nemotron 3.5 Super VL (none) (NOT the same as nemotron-3-super; flag) | mini-swe-agent | 0.3% (0.6) | 2026-10-15 |
| muse-spark 1.3 (xhigh) | Muse Code | 14.8% (3.0) | 2026-09-02 |
| kimi-k2.6, kimi-k2.7-code, minimax-m3.1-flash, nemotron-3-ultra, nemotron-3-super, gemma-4-31b, gpt-oss-120b/20b, devstral-2, devstral-small-2, qwen3-coder (all), qwen2.5-coder-7b | | not found | |

Closed context (same page): Copilot Fusion (max) 71.2% (GitHub Copilot, 2026-11-17); Claude Opus 5.5 (max) 65.8% and Fable 5.2 (max) 65.8% (Claude Code; 2026-09-22 / 2026-11-09); Gemini 4 Carbon (high) 64.5% (Antigravity CLI, 2026-10-28); Sonnet 5.5 (max) 63.9% (Claude Code); GPT-6.2 Astra (max) 62.1% (Codex, 2026-11-17).
Caveats: suffixes (0813, 1017) are checkpoint labels on the page. Same family varies widely across versions and agents (deepseek-v4-pro 0813 6.7% vs v4.1-flash 38.5%); very low numbers (deepseek-v4-pro, minimax-m3 under mini-swe-agent) may reflect harness/config effects, not just ability.

---
## 2. SWE-bench Verified
### 2a. swebench.com (official)
- Fetch of swebench.com and /verified.html returned no rows (JS-rendered). Only metadata was read: bash-only tab uses mini-SWE-agent (ReAct, bash only); release 1.x and 2.x results "are not necessarily comparable" (2.x uses tool calling). /bash-only.html returned 404. Per-model official numbers: not found.
- A search snippet (second-hand, not verified on the primary page) said the Feb 2026 official bash-only run gave GLM-5 (high) 72.8% and MiniMax M2.5 (high) 75.8%. Neither is a candidate.

### 2b. Vals.ai SWE-bench Verified (https://www.vals.ai/benchmarks/swebench)
- Independent operator run, Mini-SWE-agent harness unless stated. Snapshot 2026-09-01. Archived: Vals says the benchmark is saturated and no longer runs new models, so later models (kimi-k3.1-pro, minimax-m3.1-flash, deepseek-v4.1-flash 1017) are absent. Subset/prompt used by Vals is not stated on the fetched page, so not necessarily comparable with swebench.com numbers.
- Relevance: high in task shape (real issues, hidden tests), but saturated and public since 2024 (high contamination risk); top scores 95-97%. Useful mainly to rule out weak models.

| Model | Accuracy | Harness |
|---|---|---|
| glm-5.3 | 95.40% | Mini-SWE-agent |
| glm-5.3-flash | 92.00% | Mini-SWE-agent |
| glm-5.2 | 82.80% | Mini-SWE-agent |
| kimi-k3 | 93.40% | Mini-SWE-agent |
| kimi-k2.7-code | 78.20% | Mini-SWE-agent |
| kimi-k2.6 | 76.20% | Mini-SWE-agent |
| kimi-k3.1-pro | not found | |
| deepseek-v4-pro 0813 | 96.40% | Mini-SWE-agent |
| deepseek-v4 (base) | 77.40% | Mini-SWE-agent |
| deepseek-v4-flash 0731 (not v4.1-flash) | 88.80% | Mini-SWE-agent |
| deepseek-v4.1-flash | not found | |
| minimax-m3 | 75.00% | Mini-SWE-agent |
| minimax-m3.1-flash | not found | |
| nemotron-3-ultra | 69.00% | Mini-SWE-agent |
| nemotron-3-super | not found (Nemotron 3.5 Lightning 52.80% is a different model) | |
| mistral-large-4 | not found (Mistral Large 3: 41.40%; Mistral Medium 3.5: 66.40%) | |
| mimo-v2.6 | not found (MiMo V2.5 Pro 74.00%, V2.5 71.00%) | |
| muse-spark | version ambiguous: Muse Spark 1.2 86.60%; 1.1 82.00%; base 74.40% | Mini-SWE-agent |
| devstral-2 | 62.80% | Mini-SWE-agent |
| devstral-small-2 | not found | |
| gpt-oss-120b | 33.60% | Mini-SWE-agent |
| gpt-oss-20b | not found | |
| gemma-4-31b | not found | |
| qwen3-coder (30B/480B/next), qwen2.5-coder-7b | not found (Qwen 3.8 27B 86.00%, 3.8 Max 85.60% are other models) | |

Closed context: Claude Opus 5 97.00%; GPT-5.6 Sol 96.20%; Grok 4.6 95.60%; GPT-5.6 Terra 95.40%; Claude Fable 5 95.00%; Claude Opus 4.8 88.60%. Newest closed models (Fable 5.2, Opus 5.5) absent because archived.

---
## 3. SWE-bench Pro public (Scale AI, https://labs.scale.com/leaderboard/swe_bench_pro_public)
- Measures: harder, longer, multi-file issues from more diverse repos with hidden tests; designed to resist contamination (I did not verify the construction details on the fetched page).
- Page gives no dates. Scaffold named only for starred rows (mini-swe-agent); other rows' scaffold not listed, so do not compare starred with unstarred rows. Page says greyed rows used a 50-turn limit and cost cap, others 250 turns and no cap; which rows are which could not be read.
- Relevance: highest of the public leaderboards for TraceForge (realistic repo-level patches, hidden-test verification). Still no abstention or retrieval grading.
- Operator-run (independent).

| Model | Score (+-CI) | Scaffold |
|---|---|---|
| muse-spark 1.1 | 61.50 +-3.10 | mini-swe-agent |
| muse-spark (base) | 55.00 +-3.60 | mini-swe-agent |
| qwen3-coder-480b-a35b | 38.70 +-3.55 | not listed |
| minimax-2.1 (not m3) | 36.81 +-3.55 | not listed |
| gpt-oss-120b | 16.20 +-2.67 | not listed |
| glm-4.6 (not a candidate version) | 9.67 +-2.15 | not listed |
| glm-5.2/5.3/5.3-flash, kimi-k2.6/k2.7-code/k3/k3.1-pro, minimax-m3/m3.1-flash, deepseek-v4-*, gpt-oss-20b, nemotron-*, gemma-4-31b, mistral-large-4, mimo-v2.6, devstral-*, qwen3-coder-30b/next, qwen2.5-coder-7b | not found | |

Closed context: gpt-5.4 (xHigh) 59.10; claude-opus-4-6 (thinking) 51.90; gemini-3.1-pro (thinking) 46.10; claude-opus-4-5 45.89. Page looks stale relative to the newest closed models (no Opus 5/Fable/GPT-6 rows).

---
## 4. SWE-rebench (https://swe-rebench.com) - continuously refreshed GitHub issues
- Measures: resolved rate on fresh tasks; window fetched 2026-05-15 to 2026-07-01, 111 problems from 65 repos. Fresh tasks limit contamination for models released before the window. Scaffold for "Model" rows not named on the fetched page (details in a truncated Insights section: not read). Agent rows are products.
- Relevance: high (repo-level, hidden tests, contamination-resistant). The window predates the newest models (glm-5.3, kimi-k3/k3.1, deepseek-v4.1 etc. have no score).
- Independent (operator-run). Resolved % +-SE, Pass@5 in brackets.

| Model | Resolved % (Pass@5) |
|---|---|
| glm-5.2 [high] | 62.9 +-1.19 (81.1) |
| minimax-m3 | 47.2 +-1.13 (69.4) |
| MiMo V2.5 Pro (not v2.6) | 46.5 +-0.54 (65.8) |
| deepseek-v4-pro [high] | 40.2 +-1.29 (64.0) |
| Qwen3.6-27B (not qwen3-coder) | 31.2 +-1.68 (57.7) |
| Qwen3.6-35B-A3B | 24.7 +-0.79 (43.2) |
| kimi-k2.6, gpt-oss-120b, gpt-oss-20b, gemma-4-31b, devstral-2, devstral-small-2, qwen3-coder-30b/480b/next, deepseek-v4-flash | listed, but N/A (no result in this window) |
| glm-5.3, glm-5.3-flash, kimi-k2.7-code, kimi-k3, kimi-k3.1-pro, minimax-m3.1-flash, deepseek-v4.1-flash, nemotron-*, mistral-large-4, mimo-v2.6, muse-spark, qwen2.5-coder-7b | not found |

Closed context: Fable 5 [high] 64.5 (78.4); Grok 4.5 [high] 63.8; Opus 5 [high] 63.4; GPT-5.6 Sol [medium] 62.3; Sonnet 5 [high] 56.8; agents Junie 61.8, Claude Code 60.4. glm-5.2 is close to the top closed models here; it is the strongest independent open-model number found. The page's "open weights" column was inferred by the fetching tool, not stated by the site.

---
## 5. Aider Polyglot (https://aider.chat/docs/leaderboards/)
- Measures: 225 Exercism exercises in 6 languages; edit-format adherence and fixing via test feedback. Small self-contained tasks, public since 2024 (contamination risk). Page last updated 2025-11-20, so stale: it has none of the newer candidate versions.
- Relevance for TraceForge: low to moderate (edit-format reliability; no repo retrieval). Different aider versions per row, so not strictly comparable.

| Model | % correct | Run date / aider version |
|---|---|---|
| gpt-oss-120b (high) | 41.8% | 2025-08-06 / 0.85.3.dev |
| Kimi K2 (not k2.6+) | 59.1% | 2025-07-17 / 0.85.3.dev |
| DeepSeek-V3.2-Exp Reasoner (not v4) | 74.2% | 2025-10-03 / 0.86.2.dev |
| Qwen2.5-Coder-32B-Instruct, whole (not the 7b baseline) | 16.4% | 2024-12-26 / 0.69.2.dev |
| all other candidates, incl. qwen2.5-coder-7b, glm-*, minimax-*, nemotron-*, gemma-4, mistral-large-4, devstral-*, kimi-k2.6+ | not found | |

Closed context: gpt-5 (high) 88.0%; gpt-5 (medium) 86.7%; o3-pro 84.9%; gemini-2.5-pro 83.1% (all 2025 runs).

---
## 6. LiveCodeBench
- Official site (https://livecodebench.github.io/leaderboard.html): page showed only "Loading..."; version, window and scores not read. No official numbers retrieved.
- Measures: competitive-programming problems (generation, repair, execution, test-output prediction), date-tagged to detect contamination. Not repo-level; low relevance for TraceForge.
- Vals.ai LCB (https://vals.ai/benchmarks/lcb): independent operator run, snapshot 2026-09-01, archived. Version/problem window not stated on the fetched page. A search snippet suggested older (2025-dated) snapshots exist; contamination risk for recent models is high.

| Model | Accuracy |
|---|---|
| deepseek-v4-pro 0813 | 87.53% |
| deepseek-v4 (base) / v4-flash 0731 | 87.48% / 87.26% |
| kimi-k3 | 87.19% |
| kimi-k2.6 | 86.77% |
| kimi-k2.7-code | 82.05% |
| nemotron-3-ultra | 85.98% |
| muse-spark 1.1 | 85.91% |
| gpt-oss-120b | 83.23% |
| gpt-oss-20b | 80.39% |
| minimax-m3 | 82.15% |
| glm-5.3 / glm-5.3-flash / glm-5.2 | 80.53% / 80.51% / 69.50% |
| devstral-2 / devstral-small-2 | 51.84% / 43.18% |
| mistral-large-4, mimo-v2.6 (MiMo V2.5 Pro: 81.35%), kimi-k3.1-pro, minimax-m3.1-flash, deepseek-v4.1-flash, nemotron-3-super, gemma-4-31b, qwen3-coder-*, qwen2.5-coder-7b | not found |

Closed context: Claude Fable 5.1 90.52%; Fable 5 89.78%; Gemini 3.8 Flash 89.48%; Opus 5 89.03%. The top ~20 are within about 4 points: near saturation.

---
## 7. Arena (arena.ai / LMArena) - human preference and usage
### 7a. Agent/Code Coding Index (https://arena.ai/leaderboard/agent/code, snapshot 2026-11-18)
- Measures: Elo-like index estimated from ~1.03M real Agent Mode sessions across 68 models (task completion, sentiment, steerability, bash reliability). Usage/preference based, not hidden tests. Medium relevance (real agentic use) but confounded by user tasks and product agents.
- The fetched page showed only the top 15 with scores. Rows marked "snippet" come from search-result snippets of per-model pages (undated, unverified).

| Model | Index | Note |
|---|---|---|
| deepseek-v4.1-flash-20261017 (max) | 1,128 | fetched page; a snippet said 1,133 (rank 28): conflicting |
| glm-5.3 (max) | 1,104 (rank 35 of 65) | snippet |
| kimi-k3 (max) | 1,088 (rank 39) | snippet |
| minimax-m3.1-flash | 1,087 (rank 40) | snippet |
| glm-5.3-flash | 1,059 (rank 45 of 65) | snippet |
| muse-spark 1.1 | rank 61, no score | fetched page |
| Nemotron 3.5 Super VL (not nemotron-3-super) | rank 64, no score | fetched page |
| kimi-k3.1-pro, glm-5.2, minimax-m3, mimo-v2.6, mistral-large-4, nemotron-3-ultra | named on page, no score | |

Top: Claude Fable 5.2 (Max) 1,489; Opus 5.5 (Max) 1,373; GPT-6.2 Astra (Max) 1,338; Sonnet 5.5 (Max) 1,329; Gemini 4 Neon (High) 1,325 (preliminary).

### 7b. WebDev Arena (lmarena.ai/leaderboard/webdev), search summaries only, not primary-verified
Kimi K3-max 1675 vs Claude Opus 5-max 1686 (2026-08-06 snapshot); another aggregator listed Kimi K3 at 1657.9 (data through Sep 2026); MiMo-V2.6-Flash rank 17, 1634 (Oct 17 listing). No GLM or DeepSeek entries found. Front-end generation: low relevance.

---
## 8. Artificial Analysis
- Coding Index: not found (fetched page lacked it). Intelligence Index is general, not coding, and is not comparable with anything above. Secondary reports (unite.ai/officechai): glm-5.3 60 (2026-08-18), kimi-k3 60, glm-5.3-flash 57, deepseek-v4-pro 53. The AA page itself showed kimi-k3.1-pro 46 and deepseek-v4.1-flash 1017 (max) 33; these conflict in scale with the earlier numbers, so probably a different index version. Flag as incomparable.

## 9. Not retrieved / excluded
- BigCodeBench, tau-bench, GSO, official swebench.com rows: not retrieved, not found.
- Excluded unverified aggregator numbers: DeepSeek-V4-Pro-Max SWE-bench Verified 80.6%, Kimi K2.6 80.2%, DeepSeek-V4-Pro-Max LiveCodeBench 93.5% (2026-10-21), Kimi K2.6 LiveCodeBench v6 0.896 (llm-stats). Not independent, harness unknown.
- Inconsistency to note: Vals Verified gives deepseek-v4-pro 0813 96.4%, but Terminal-Bench 4.1 gives the same checkpoint 6.7% and SWE-rebench gives deepseek-v4-pro 40.2%. Saturation/contamination on Verified and harness differences both plausible. Do not average across benchmarks.

## 10. Contamination summary
- SWE-bench Verified, Aider Polyglot, LiveCodeBench (old windows): public and long-lived, likely seen in training; saturated at the top. Floor-check only.
- SWE-rebench: time-windowed fresh issues, best contamination control, but the window (May-Jul 2026) predates the newest models.
- SWE-bench Pro: built to resist contamination, but the public split is public. Terminal-Bench 4.1: canary string only.
- Arena indices: no test-set contamination, but preference/usage-based.

## 11. Which evidence best predicts TraceForge-style tasks
Best: SWE-rebench (fresh, repo-level, hidden tests, pass@k), then SWE-bench Pro (hard, multi-file, hidden tests), then Terminal-Bench 4.1 (tool-calling and verification loops, harness-confounded). Verified only rules out weak models. Aider and LiveCodeBench are weak proxies. No retrieved benchmark measures abstention, evidence retrieval or minimal-patch discipline; those need TraceForge's own evals.

Open candidates with the strongest independent evidence:
1. glm-5.2: SWE-rebench 62.9%, near the top closed models. glm-5.3: Vals Verified 95.4% and Terminal-Bench 41.2%, but no fresh-task result.
2. kimi-k3.1-pro: Terminal-Bench 59.7%, best open entry there (single run, wide CI). kimi-k3: strong Verified and WebDev but 23.0% on Terminal-Bench (older checkpoint).
3. minimax-m3: SWE-rebench 47.2%; mixed (Terminal-Bench 7.6% under mini-swe-agent).
4. deepseek-v4.1-flash: Terminal-Bench 38.5%, Arena Coding Index 1,128; deepseek-v4-pro results inconsistent across harnesses.
5. muse-spark: SWE-bench Pro 55-61.5% (mini-swe-agent) but weak Terminal-Bench (14.8%).
Weak or missing: gpt-oss-120b (Pro 16.2, Verified 33.6, Aider 41.8), devstral-2 (Verified 62.8, LCB 51.8); mistral-large-4, nemotron-3-super, gemma-4-31b, qwen3-coder and qwen2.5-coder-7b have essentially no current independent results (mostly not found).
Best overall regardless of price: Claude Fable 5.2 / Opus 5.5 (Terminal-Bench 65.8%, Arena Coding Index 1st/2nd), with GitHub Copilot Fusion (71.2%) top on Terminal-Bench as a product/agent rather than a single model. SWE-rebench has Fable 5 at 64.5%.
