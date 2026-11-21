# Limits report (P0-S06)

Purpose: measure where the approach breaks before Phase 1 builds on assumptions. Every number below comes from a saved, rerunnable run. Part A is done; Part B (model probe) is Ruhan's and is still to come.

## Part A — Retrieval spike (Rafique)

**Run:** `task spike:retrieval`. Raw results: `spikes/retrieval/results/retrieval.json`. Python 3.12.13, ripgrep 15.2.0, Windows 11. Two consecutive runs gave identical ranks.

**Setup.** A toy shop (`spikes/retrieval/toyshop/`: 7 Python files + `compose.yaml`, 189 lines, 22 functions, 5 config keys). Five faults, each injected into a fresh copy and **actually run**, so every traceback is real:

| Fault | Class | Distance (graph hops from nearest trace frame to cause) | Real error line |
|---|---|---|---|
| F1 empty cart | code | 0 | `IndexError: list index out of range` |
| F2 zero qty | code | 0 | `ZeroDivisionError: division by zero` |
| F3 Redis host typo (`REDIS_HOST=redsi`) | config | 1 | `socket.gaierror: [Errno 11001] getaddrinfo failed` |
| F4 pool size 0 (`DB_POOL_SIZE=0`) | config | 1 | `ValueError: pool size must be positive, got 0` |
| F5 qty parsed as string (bug in `cart.parse_qty`, not on the stack) | code | 2 | `TypeError: can't multiply sequence by non-int of type 'float'` |

The distance computed from the graph matched the intended distance for all 5 faults.

**Methods** (weights fixed before the first run, not tuned afterwards):
- **R0 ripgrep:** `rg -i -F` with the raw function names from the trace plus the error-line words; functions ranked by hit count. No trace anchoring.
- **Trace-only:** the project's trace frames, innermost first; nothing else.
- **L:** trace frames first (anchor), then BM25 over function and config-key text.
- **G:** same anchors; other nodes scored by normalized BM25 + 1/(1+hops) if within 2 hops of an anchor (calls in both directions, config reads, settings field → config key).

**Rank of the true cause** (lower is better; — = not found):

| Fault | Distance | R0 ripgrep | Trace-only | L | G |
|---|---|---|---|---|---|
| F1 | 0 | 6 | 1 | 1 | 1 |
| F2 | 0 | 2 | 1 | 1 | 1 |
| F3 | 1 | — | — | — | 6 |
| F4 | 1 | 5 | — | 5 | 5 |
| F5 | 2 | — | — | — | 16 |

| Method | Recall@1 | Recall@5 | Recall@10 | MRR | Median time/query |
|---|---|---|---|---|---|
| R0 ripgrep | 0.0 | 0.4 | 0.6 | 0.173 | 69.3 ms |
| Trace-only | 0.4 | 0.4 | 0.4 | 0.400 | 3.1 ms |
| L | 0.4 | 0.6 | 0.6 | 0.440 | 3.8 ms |
| G | 0.4 | 0.6 | 0.8 | 0.486 | 3.6 ms |

**Code map:** 694 characters (≈173 tokens, estimated as chars/4) for the whole toy app.

### What this shows
1. **Distance 0 is easy for everything except plain grep.** The trace alone puts the cause at rank 1. ripgrep finds the right area but never ranks the cause first, because hit counts favour the callers that repeat the same names (F1 rank 6).
2. **Config faults are where the graph earns its place.** For F3 the error message doesn't even contain the bad host (Windows' `getaddrinfo` error omits it), so no lexical method can find `REDIS_HOST`. Only G reached it, through the `cfg.redis_host` → `REDIS_HOST` binding (rank 6). This also confirms that **effective-config evidence is essential**: the value `redsi` is visible only there.
3. **Two hops through a call chain fails with simple hop scoring** (F5, rank 16). The bug sits in a function that already returned (`cart.parse_qty`). Many 1-hop neighbours, and the `settings()` hub that links to every config key, outrank it.
4. **Trace anchors crowd out the top 5.** With 2–4 project frames on the stack, anchoring every frame leaves only 1–3 slots for anything else. That is why G finds F3 at rank 6 and F4 at rank 5, just behind 4 anchors.
5. ripgrep is ~20× slower here only because it starts a process per query. That is irrelevant at this size but worth knowing.

### Recommendations
- **D18 (baselines): confirmed.** Keep R0 ripgrep and trace-only in E1; they separate "the trace already says it" from real retrieval gains.
- **D22 (code map): confirmed.** It is cheap (~173 tokens for 22 functions) and should be given to both arms.
- **New D32 (provisional): anchor only the innermost 2 project frames.** Other frames become normal candidates with a bonus, and E1 reports Recall@5 and Recall@10 so anchoring can't hide misses.
- **For P2-S02/P2-S03 (graph and retrieval design):**
  - weight edges by type (config binding > call);
  - down-weight hub nodes such as the `settings()` factory;
  - add a "returned value used downstream" edge (data flow from `load_items` into `checkout`), so causes that already returned (like F5) become reachable.
  - Decide these weights on the **dev split** only.

### Limits of this evidence
Five faults in a 189-line app, written by the same person who wrote the ranking (author bias; see D28). This shows direction and failure modes, not effect sizes. Effect sizes come from E1 on the frozen dataset.

## Part B — Model probe (Ruhan)
Not run yet. Owner: Muhammad Ruhan Kamran. See [P0-S06](../plans/phase-0-foundation/step-06-feasibility-prototype.md#e-implementation-instructions), Part B. It will fill in:
- read limit per file size;
- write limit and edit validity;
- unified diff vs search/replace;
- per-edit code quality;
- real free-tier rate limits and latency, for Devstral and Qwen2.5-Coder-7B;

plus recommendations for D19 (edit format), D20 (context budget) and D21 (primary model).
