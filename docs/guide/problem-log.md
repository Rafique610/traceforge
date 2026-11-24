# Problem log and decisions

> **Status sync 2026-11-25.** This chapter was written on 2026-11-21 and parts are historical. Current status of Ruhan's 20 primary tasks: **none COMPLETE & VERIFIED**; 11 IMPLEMENTED NOT VERIFIED, 7 PARTIALLY COMPLETE, 2 NOT STARTED (conditional). Nothing is reviewed by Rafique or approved by the owner. Authoritative: `docs/plans/RUHAN_TASK_TRACKER.md`. Where this chapter says Rafique's components are absent, there is no experiment, or the model is undecided, that is stale: the lab, sandbox, evidence, graph, retrieval, metrics and a 184-case frozen dataset exist; a reduced RC1 evaluation exists in `results/final` (35 sites at replicate 0, 12 at replicate 1, 8 at replicate 2; AxForge `glm-5.3-flash`); the team is two members (Rafique, Ruhan).


Back to [TraceForge Explained](TraceForge-Explained.md). Each entry: what happened, why, what was done, how to check, status. Date of all entries below: **2026-11-21** (the working session). Where the repo holds no record beyond the session report, that is stated.

## Problems

### P-001 Qwen2.5-coder prints tool calls as JSON text
- **Symptom.** With Ollama and `qwen2.5-coder:7b`, a request offering tools returned the call as a text message (`{"name": ..., "arguments": {...}}`) with an empty `tool_calls` field, so the agent saw "no tool call".
- **Fix.** `tool_calls_from_text()` in `backend/traceforge/agent/gateway.py`. It accepts the text only if it parses as JSON, has exactly the keys `name` and `arguments`, and the name is one of the tools offered in this request. Used as a fallback only when the provider returned no real tool calls.
- **Why strict.** An unknown tool name or extra keys are refused, so a model (or an injected instruction) cannot invent tools through text.
- **Test.** `test_tool_call_printed_as_json_text_is_accepted_only_for_offered_tools` in `backend/tests/agent/test_gateway.py` (accepts a valid offered call, rejects `delete_all`, plain prose, missing `arguments`, and a call with no tools offered).
- **Status.** Fixed in the working tree.

### P-002 `uv` concurrent runs hang
- **Symptom (session report).** Running several `uv` commands at the same time hung.
- **Fix / workaround.** **Not recorded in the repo.** Pending: confirm the cause (likely shared cache or environment lock) and write down the rule, for example run `uv` commands one at a time. This guide does not assert a cause.
- **Status.** Pending documentation.

### P-003 `C:` drive 91% full: models and caches moved to `D:`
- **Facts.** Decision B3 (`docs/orchestration/DECISIONS.md`) and the handoff note: `C:` had 49 GB free of 534 GB (91% used); `D:` had 186 GB free. Docker data (about 34 GB) was the largest consumer found.
- **Fix.** Ollama store for future pulls `D:\AI\Models\ollama` (`OLLAMA_MODELS`), `HF_HOME` = `D:\AI\Caches\huggingface`, `UV_CACHE_DIR` = `D:\AI\Caches\uv`. Existing models on `C:` (all-minilm, medgemma:4b, qwen3.5:4b, about 6.2 GB) were left untouched, but they are not visible to the restarted Ollama server. The `qwen2.5-coder:7b` pull was started to `D:` (log `D:\AI\pull-qwen.log`, per STATE.md).
- **Reverse.** Unset the variables and restart Ollama.
- **Status.** Done (machine-level).

### P-004 Mistral direct free API not usable, so the gateway became provider-agnostic
- **Facts.** The original plan made the Mistral free tier with a pinned Devstral model the primary LLM. The provider research found that Devstral 2 needs paid API access per Mistral's announcement and that free API usage is the limited "Experiment" plan; whether Devstral works there is unverified. The user's note in decision B4: direct Mistral free access is uncertain and the budget is USD 0.
- **Fix.** The gateway supports `ollama`, `openrouter`, `mistral`, `groq` through the OpenAI-compatible client, with a **free-only guard**: default allowlist is `ollama` and `openrouter`, and OpenRouter model ids must end with `:free`. A Mistral or Groq call is refused while `llm_free_only` is true. Decision B4 supersedes the wording of step P1-S05.
- **Open.** The real primary model, Q1 and ADR 0001 are pending.
- **Tests.** `test_free_only_guard_refuses`, `test_free_only_allows_free_openrouter_and_explicit_allowlist`.

### P-005 `corepack` EPERM, so pnpm was installed with npm
- **Symptom (session report).** `corepack enable` failed with a permission error (EPERM) on Windows without admin rights.
- **Fix.** Install pnpm through npm. The README already documents this: "`corepack enable`, or `npm i -g pnpm` if that needs admin".
- **Status.** Resolved.

### Other open flags found while writing this guide
- README status text is behind the code (see [main page](TraceForge-Explained.md#7-known-documentation-gaps-read-this)).
- The agent patch stage (unified diff) and the repair loop (SEARCH/REPLACE) use different edit formats; they are not connected.
- Migration `0001_incidents.py` has never been run on Postgres.
- STATE.md says the 4 Ollama models on `C:` are not visible to the restarted server; re-pull or move if needed.

## Decisions

The decision log is **`docs/orchestration/DECISIONS.md`** (Stage B). Current entries:

| ID | Short meaning |
|---|---|
| B1 | The task list is 20 steps for Ruhan (P0:4, P1:4, P2:3, P3:2, P4:2, P5:2, P6:3); "17 primary + 3 supporting" is the same set |
| B2 | The old `INSTRUCTIONS.md` rule of autonomous commit and push is not applied; commits are forbidden in this assignment |
| B3 | Models and caches on `D:` (see P-003) |
| B4 | Provider-agnostic gateway with free-only guard (see P-004) |
| B5 | Local branch `ruhan/stage-b-work`; parallel agents share one tree with disjoint folder ownership instead of worktrees |

Larger design decisions (D18 baselines, D19 edit format, D20 context budget, D21 primary model, D22 code map, D26 replicate in cache key, D28 author bias, D31 test-literal check, D32 anchor only 2 frames) live in `docs/plans/DECISIONS_AND_OPEN_QUESTIONS.md` and `docs/research/limits-report.md`. I did not re-read that plan file line by line for this guide; check it for the authoritative wording.
