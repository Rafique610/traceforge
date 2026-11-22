# TraceForge model benchmark (Phase 2/3), 2026-11-22

## Status: NOT RUN for any of the 7 requested models
Your rule: a model without a verified free API must not receive a coding-performance score. All seven are therefore **N/A**. No tests were run, no scores were assumed, and nothing was spent.

| # | Model | API-verified free? | Phase 2/3 tests run | Score |
|---|---|---|---|---|
| 1 | GLM 5.2 | no (HTTP 404; paid elsewhere) | none | N/A |
| 2 | Qwen3 Coder 480B | no (HTTP 404; other routes need verification) | none | N/A |
| 3 | Qwen3 Coder 30B (Synap) | **not yet** (needs a Google sign-in and key from you) | none | N/A. The only candidate that can still become testable |
| 4 | DeepSeek V4 Flash | no (HTTP 404; paid) | none | N/A |
| 5 | DeepSeek V4.1 Flash 1017 | no (HTTP 404; app-only or unverified elsewhere) | none | N/A |
| 6 | Kimi K3 | no (paid only) | none | N/A |
| 7 | Kimi K2.7 Code | no (paid only) | none | N/A |

## What can be tested at $0 today (context only; not part of the 7)
Existing real TraceForge results, kept unchanged:
- Local `qwen2.5-coder-7b` got 0/4 cause classes on the seed cases with the real pipeline; the rules baseline got 2/4.
- `nvidia/nemotron-3-ultra-550b-a55b:free` fixed 10/10 in the format test and passed 2 of 3 smoke tasks (it fell for the misleading-warning task).
- See `docs/plans/RUHAN_AUDIT.md` (Addendum 2) and `docs/research/TRACEFORGE_FREE_MODEL_RECOMMENDATION.md`.

## Test plan, ready for any model that becomes API-verified
Identical for every model:
1. The fixed 8-task smoke set (`spikes/free_model_smoke/`): root cause, misleading evidence, abstention, injection, minimal patch, schema compliance, repeatability.
2. The 4 validated seed cases through the real pipeline (real evidence, retrieval and sandbox).
3. Multi-file and feature tasks in isolated worktrees.

Same snapshot, prompts, tools and budgets; temperature 0; 3 attempts. Scoring weights as you specified (root cause 20, multi-file 20, implementation 15, regression tests 10, understanding 10, recovery 10, tools 5, security 10).

Request budget: the smoke set needs about 13-53 requests per model per pass. Synap's free key allows 10-50 requests a day with 4,096 output tokens, so a pass would take several days, using the harness's `--max-requests` cap and its resume cache.
