# TraceForge primary-model recommendation (2026-11-21) — for Ruhan's approval

Nothing has been changed: gateway, conditions and configs are untouched. This is a recommendation only. Evidence: `CODING_LLM_COMPARISON.md`, `_benchmarks_raw.md`, `REDDIT_CODING_MODEL_CONSENSUS.md` (no Reddit data could be retrieved).

## The honest answer in one paragraph
The objectively strongest open models on your Ollama account (glm-5.2, kimi-k3.1-pro) are **not free**: the account has $0 allowance and Ollama's pricing page lists no free plan, so none can be used at a guaranteed $0. Devstral is retired. At a strict $0 the only models we have actually run are **`nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter** and **local `qwen2.5-coder:7b`**. The recommendation therefore splits into what is best *for $0 now* and what would be best *if a small allowance were ever approved*.

## Recommended primary model (at $0)
**`nvidia/nemotron-3-ultra-550b-a55b:free` (OpenRouter), with local `qwen2.5-coder:7b` as the fallback and baseline.**

Why it wins over the alternatives we can use for free:
- Verified working in our gateway: native tool calling, 5–7 s latency, free-only guard allows it, key limit $0 (see `free-model-providers.md`).
- Independent evidence for the same model family: SWE-bench Verified 69.0% (Vals, mini-SWE-agent) and LiveCodeBench 85.98%; no SWE-rebench/Terminal-Bench result (nf). Evidence is modest and Verified is contaminated.
- On our own small test (10 fixes, same cases): search/replace fixes exactly correct 10/10 vs 7/10 for local Qwen; unified diff 3/10 vs 0/10 (`limits-report.md` addendum). n=10, single run — direction only.
- In real sample runs it diagnosed the config and code cases correctly; its weaknesses seen: a reasoning model needs an output budget (fixed), and on the abstain case it printed a malformed tool call and made 3 invalid calls.
Why it beats local Qwen2.5-Coder-7B: the 7B model wrongly abstained on the code sample, failed multi-line edits at 20+ lines in the probe, and needs ~20–200 s per call on this hardware; it has no current independent benchmark evidence.

## What it cannot do (important)
- **Throughput:** OpenRouter's free models are limited to a few dozen requests per day (documented 20/min, 50/day without purchased credits; not re-measured). The full experiment (~1,700 runs, multiple calls each) cannot be run on it. It is enough for development, pilots and small dev-set runs only.
- **Experiment validity:** one experiment must not mix models. The full 2×2 at scale can run at $0 only on local Qwen (slow, weaker), or be scoped down to the cases a free daily quota allows (spread over days, cache enabled).
- **Stability:** free models on aggregators can change or disappear; pin the ID and record the date; re-verify before each experiment day.
- Data terms of the free provider are unverified.

## Ranking summary
| Ranking | Result |
|---|---|
| A. Best overall (price ignored) | closed frontier models; among open: glm-5.2, kimi-k3.1-pro |
| B. Best through your Ollama account at $0 | none confirmed free; plausible-but-unverified: gpt-oss:20b/120b (weak) |
| C. Best for TraceForge (price ignored) | glm-5.2 > kimi-k3.1-pro > glm-5.3 ≈ deepseek-v4.1-flash > kimi-k2.6 > nemotron-3-ultra > ... |
| C at verified $0 | nemotron-3-ultra:free > qwen2.5-coder:7b |

## If you ever want a stronger model (decision for you, not made)
Cheapest credible upgrade paths if a small allowance is explicitly approved: `deepseek-v4.1-flash` or `glm-5.3-flash` (≈ $7–13 for the whole experiment by the rough estimate in the comparison) or `glm-5.2` (≈ $80, best independent debugging evidence). These are planning estimates from assumed token counts, not quotes. Until you approve spending, nothing changes.

## Confidence
- Free-only recommendation (Nemotron `:free` + Qwen fallback): **medium-high** that it is the best *verified* $0 option; **low** on how it compares with models we cannot test.
- Ranking of unverified/paid models: **medium-low** (benchmark pages summarised by a small model; thin community data; no Reddit).
- Compatibility with the gateway: **high** for the two tested models, **unknown** for the others.

## What I need from you
Approve (or change) the primary model. On approval I will pin the model ID in `evaluation/conditions/*.json` and ADR 0001, keep Qwen as fallback, keep Devstral recorded as "retired/unavailable", and plan the experiment scale to fit the free quota. Without approval nothing changes.
