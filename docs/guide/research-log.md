# Research log

> **Status sync 2026-11-25.** This chapter was written on 2026-11-21 and parts are historical. Current status of Ruhan's 20 primary tasks: **none COMPLETE & VERIFIED**; 11 IMPLEMENTED NOT VERIFIED, 7 PARTIALLY COMPLETE, 2 NOT STARTED (conditional). Nothing is reviewed by Rafique or approved by the owner. Authoritative: `docs/plans/RUHAN_TASK_TRACKER.md`. Where this chapter says Rafique's components are absent, there is no experiment, or the model is undecided, that is stale: the lab, sandbox, evidence, graph, retrieval, metrics and a 184-case frozen dataset exist; a reduced RC1 evaluation exists in `results/final` (35 sites at replicate 0, 12 at replicate 1, 8 at replicate 2; AxForge `glm-5.3-flash`); the team is two members (Rafique, Ruhan).


Back to [TraceForge Explained](TraceForge-Explained.md). Only results that exist as saved files are reported. Everything else is **pending**.

## 1. Retrieval feasibility spike (P0-S06 Part A, Rafique)

Source: `docs/research/limits-report.md`; raw data `spikes/retrieval/results/retrieval.json`; command named there: `task spike:retrieval` (this task is **not** in this tree's `Taskfile.yml`; the spike code is in `spikes/retrieval/`). The report says two consecutive runs gave identical ranks.

**Setup.** A toy shop (`spikes/retrieval/toyshop/`: 7 Python files plus `compose.yaml`, 189 lines, 22 functions, 5 config keys). Five faults were injected into fresh copies and actually run, so the tracebacks are real.

| Fault | Class | Distance | Real error |
|---|---|---|---|
| F1 empty cart | code | 0 | `IndexError` |
| F2 zero quantity | code | 0 | `ZeroDivisionError` |
| F3 Redis host typo | config | 1 | `socket.gaierror` |
| F4 pool size 0 | config | 1 | `ValueError` |
| F5 quantity parsed as string | code | 2 | `TypeError` |

**Four methods compared:** R0 (ripgrep text search), trace-only (just the stack frames), **L** (trace anchors then BM25), **G** (same anchors plus normalized BM25 plus `1/(1+hops)` within 2 hops, with calls in both directions and config bindings). Weights were fixed before the first run.

**Rank of the true cause** (lower is better; "-" = not found):

| Fault | Distance | R0 | Trace-only | L | G |
|---|---|---|---|---|---|
| F1 | 0 | 6 | 1 | 1 | 1 |
| F2 | 0 | 2 | 1 | 1 | 1 |
| F3 | 1 | - | - | - | 6 |
| F4 | 1 | 5 | - | 5 | 5 |
| F5 | 2 | - | - | - | 16 |

| Method | Recall@1 | Recall@5 | Recall@10 | MRR |
|---|---|---|---|---|
| R0 ripgrep | 0.0 | 0.4 | 0.6 | 0.173 |
| Trace-only | 0.4 | 0.4 | 0.4 | 0.400 |
| L | 0.4 | 0.6 | 0.6 | 0.440 |
| G | 0.4 | 0.6 | 0.8 | 0.486 |

(*Recall@k* = share of cases where the true cause is in the top k results. *MRR* = mean of 1/rank of the true cause.)

**What it shows (the report's own reading):**
1. Distance 0 is easy for everything except plain grep; the trace alone ranks the cause first.
2. Config faults are where the graph earns its place: for F3 the error message does not contain the bad host, so only G, via the code-to-config-key binding, reached `REDIS_HOST`. This also shows effective-config evidence is essential.
3. A 2-hop chain (F5) fails with simple hop scoring: hub nodes such as the `settings()` factory and many 1-hop neighbours outrank the cause.
4. Anchoring every trace frame crowds the top 5.

**Limits (stated in the report):** only 5 faults in a 189-line app written by the person who wrote the ranking (author bias). It shows direction and failure modes, not effect sizes. Real effect sizes must come from the frozen dataset (Phase 3-4), which does not exist yet.

**Recommendations recorded:** keep ripgrep and trace-only baselines (D18 confirmed); give the code map to both arms (D22 confirmed, about 173 tokens for 22 functions); provisional D32: anchor only the innermost 2 project frames; weight config-binding edges above call edges, down-weight hubs, add a data-flow edge, and tune weights on the dev split only.

## 2. Free model provider research (Ruhan, 2026-11-21)

Source: `docs/research/free-model-providers.md`. Method: official pages read through a summarizing fetch tool; no signup or API call made. The document marks many items **UNVERIFIED**; the highlights:

| Provider | Finding | Consequence |
|---|---|---|
| Local Ollama | Free and unlimited on own hardware | Recommended primary for experiments (pinned tag) |
| OpenRouter `:free` | 20 requests/minute; 50/day if under 10 credits ever bought, 1000/day otherwise; dropping `:free` bills per token; `openrouter/free` router is non-deterministic | Allowed with a hard `:free` check; never the router |
| Mistral | Free API usage is the "Experiment" plan; Devstral 2 needs paid API access per the Jan 2026 announcement; whether Devstral is callable on the free tier is UNVERIFIED | Not assumed free (decision B4) |
| Groq | Free-plan numbers UNVERIFIED | Spare only |
| Gemini free tier | Free-tier content is used to improve Google products | Non-sensitive prompts only |
| Ollama Cloud, Cerebras | Need credits or a card | Excluded under USD 0 |
| GitHub Models | Retired as of 2026-07-30 | Not available |
| OpenCode free models | Rotating, some retain or train on data | Dev assistance only |

The document's own warnings: free models rotate or deprecate; never enable auto-recharge; some free tiers train on data; treat free backends as non-reproducible even at temperature 0, and record model, provider, date, seed and temperature per result. The gateway's free-only guard implements the "hard-fail on any non-`:free` id" idea (see [tech stack](tech-stack.md)).

## 3. Model probe (P0-S06 Part B): pending

Not run. It should measure read limits per file size, write limits, unified diff vs SEARCH/REPLACE, edit quality, and real free-tier limits for Devstral and Qwen2.5-Coder-7B, and settle D19 (edit format), D20 (context budget) and D21 (primary model). Until then: the context budget in `config.py` is a **placeholder** (`agent_context_budget_chars = 12000`, comment "D20 placeholder until the P0-S06 measured limit"); the edit format is provisional (repair uses SEARCH/REPLACE, the agent patch stage requests a diff); the primary model is undecided. ADR 0001 (primary model) is **not written** (`docs/adrs/` does not exist).

## 4. Local model observation

`qwen2.5-coder:7b` through Ollama sometimes prints a tool call as plain JSON text instead of using the tool-call field. The gateway now accepts that form under strict rules (see [problem log](problem-log.md)). This is one observation from the smoke work, not a measured rate.

## 5. Open research and project questions

From `docs/orchestration/DEPENDENCY_MAP.md`, the handoff notes and the checklist (all **pending**):
- Q1: which hosted free model, with real limits (blocks experiments).
- Q3: ANSWERED-CONDITIONAL. The 18 Nov 2026 supervisor email gives written permission to proceed after incorporating 13 changes; written confirmation of the revised proposal itself is not on disk (P0-S04; evidence `D:\TraceForge\Assignment_3_TraceForge\Evidence\Supervisor_Email_Response.txt`).
- Q7: where to host the public demo.
- Where the user's extra research concerns ("boundary prototype") live: no step is assigned (checklist, ambiguity 3).
- All experiments (E1 retrieval-only, L0 vs G0, full 2x2 with 3 replicates, model sensitivity, BugsInPy subset) are Phases 4-5 and blocked on Rafique's tracks and a frozen dataset.
