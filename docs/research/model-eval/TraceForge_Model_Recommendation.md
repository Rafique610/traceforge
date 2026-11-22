# TraceForge model recommendation (from the 7-model study), 2026-11-22

## Answer
**None of the seven requested models can be recommended: none has a verified free API today, and none was coding-tested.** Four are dead on OpenRouter (HTTP 404), two are paid-only, and one (Qwen3 Coder 30B on Synap) has a stated free key but needs your sign-in before any real request is possible. Per your rules, nothing is scored on assumptions.

## Final-decision questions
1. **Strongest at debugging TraceForge:** cannot be determined. No model in the set was tested.
2. **Strongest at multi-file changes:** cannot be determined.
3. **Best at autonomous workflows:** cannot be determined.
4. **Fewest incorrect diagnoses:** cannot be determined. For context only: Nemotron 3 Ultra `:free`, which is not in this set, was fooled by the misleading-log task.
5. **Most reliable through a free API:** no model of the seven is reliably free. The only provider claim of free API access is Synap's qwen3-coder-30b, with tiny limits (10-50 requests a day, 4K output) from an unproven provider.
6. **Primary cloud model:** unchanged from the earlier study: `nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter (verified working, $0, 50 requests a day), provisional and awaiting your approval. It is not one of the seven.
7. **Fallback:** local `qwen2.5-coder:7b` (unlimited, weak). Synap qwen3-coder-30b only as a low-volume pilot if you sign in.
8. **Close to Claude-level on our tasks?** No evidence for any of them. No free option was close in the independent benchmarks either (see the earlier benchmark comparison).

## What would change this
- You sign in to Synap and create a key (steps below). I could then run the fixed smoke set on `qwen3-coder-30b` within its daily limits and report real results.
- You approve a small paid allowance. Many of these models would then become testable (for example DeepSeek V4.1 Flash at roughly $0.05-0.15 per 1M input tokens on OpenRouter). That is your decision and it has not been made.
- A free route to one of the others appears. Re-check OpenRouter's catalog daily, since free periods and rosters change without notice.

## Steps only you can do (Synap pilot, optional)
1. Open https://synap402.com/free.html and read its free-tier rules and terms (https://synap402.com/terms.html). The terms prohibit circumventing quotas, so use one account only.
2. Sign in with your own Google account and create a free key (it starts `sk-pool-`).
3. Add it to `.env` yourself as `TRACEFORGE_SYNAP_API_KEY=...` using the PowerShell prompt method. Never paste the key in chat.
4. Tell Claude. A small gateway change is then needed (a free-only "synap" profile with base URL `https://synap402.com/v1`). I will ask for your approval before editing the gateway.

Cautions: only synthetic or public fixtures go through it, and the pilot is tiny (see limits).
