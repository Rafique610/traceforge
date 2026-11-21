# Limits report (P0-S06)

Purpose: measure where the approach breaks before Phase 1 builds on assumptions. Every number below comes from a saved, rerunnable run. Part A is done; Part B (model probe) is Ruhan's and is below.

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

**Run:** from `backend/`: `.venv\Scripts\python.exe ..\spikes\model_probe\probe.py --exp all` (single CLI; `--exp read,write,format,rate`). Raw results including every model reply: `spikes/model_probe/results/{read_limit,write_limit,format_comparison,rate_latency,environment}.json`; gateway call log `results/llm_calls.jsonl`. Replies are cached in `spikes/model_probe/.cache/llm`, so a rerun reproduces the same numbers without calling the model. All calls went through `traceforge.agent.gateway.chat` (temperature 0, seed 0, strictly sequential, per-call timeout 1800 s).

**Scope (read this first).** One model only: **Ollama `qwen2.5-coder:7b` (Q4_K_M)**, local. **Mistral/Devstral and every cloud model were NOT RUN** (no keys; the $0 rule forbids paid calls). So the plan's "run on both models" is half done and **D21 cannot be decided from this evidence**. The script accepts `--provider openrouter --model <id>:free --ctx <n>` for later with no code change (the gateway `:free` guard still applies); nothing cloud was called.

**Machine:** GTX 1660 SUPER (6144 MiB), about 1.0 GB free RAM at start, Windows 11, Ollama 0.40.16. At `num_ctx` 16384 Ollama kept 4.26 GB of the 5.84 GB model+KV cache in VRAM; the rest runs on CPU/RAM, which is why decoding is slow (below).

**Context window.** Ollama's default is 4096 tokens, and its `/v1` (OpenAI) endpoint ignores `options.num_ctx` (tested: `ollama ps` still showed 4096), so the gateway cannot set it. Without touching gateway request code I created a Modelfile variant `qwen2.5-coder-7b-ctx16k` (`FROM qwen2.5-coder:7b`, `PARAMETER num_ctx 16384`; weights are shared, only metadata is new) and ran everything against it. 16384 is the largest value tried; 32768 (the model's trained maximum) was not tried because the KV cache plus 1 GB free RAM made it unsafe. The only gateway change: `ModelResponse.finish_reason` is now recorded, to detect truncated replies.

### Design (all synthetic, generated by `spikes/model_probe/codegen.py`)
- Files are assembled from about 19 realistic function/class templates (dataclasses, stores, validators, parsers, helpers) across modules of at most 200 lines. One function has one planted bug (off-by-one, wrong comparison, wrong operator, ...). The prompt gives a behavioural symptom, never the function or line.
- Read test: all files shown with line numbers; the model answers `{"file","line"}`. 3 tries per size, each with a different bug type and position (20/50/80 % of the code). "Exact" = right file and exact line; "within 2" is also reported.
- Write/format tests: search/replace blocks parsed and applied with `repair.edits`; quality via `ast.parse`, ruff (E,F,W, new errors only) and `repair.policy` (`check_paths` for test-file touches, `check_patch` for the 60-line cap).

### 1. Read limit (locate a known bug)
| File size (lines) | Prompt tokens (mean, real) | Right file | Exact line | Within 2 lines | Mean latency | Truncation |
|---|---|---|---|---|---|---|
| about 120 (1 file) | 1,515 | 3/3 | 2/3 | 2/3 | 21 s | none |
| about 320 (2 files) | 4,066 | 3/3 | 1/3 | 2/3 | 45 s | none |
| about 1,050 (6 files) | 12,926 | 2/3 | 1/3 | 2/3 | 197 s | none (prompt fit in 16,384) |
| about 3,000 | NOT RUN | | | | | estimated 30k tokens, more than the 16,384 ctx; a larger ctx is unsafe on this machine |
| about 6,000 | NOT RUN | | | | | same reason |

Cost is about 12.9 real tokens per line of generated Python (with line-number prefixes). With n=3 there is no clean decay curve: exact-line accuracy is 2/3 at 120 lines and 1/3 at both 320 and 1,050 lines. Misses were mostly near the right function (off by 1 to 3 lines) or the wrong function; every answer is in the JSON. Honest reading: this model is not reliable at naming the exact faulty line from a whole file at any tested size (never above 2/3), and the 1,050-line case also lost the file once.

### 2. Write limit (search/replace, N lines that must change)
Task: `shop/rates.py` where N `tax_*` functions have a wrong return line (plus N/4 correct decoys) and a visible test file; fix all. 2 variants per size (different seeds). `max_tokens` 6000.

| Lines needing a change | Reply truncated | Valid blocks | Edit applies (`repair.edits`) | Lines actually fixed | Test file touched | Note |
|---|---|---|---|---|---|---|
| 5 | 0/2 | 2/2 | 2/2 | 1 of 5 (both runs) | 0/2 | fixed one function and stopped; parses, 0 new ruff errors |
| 20 | 0/2 | 0/2 | 0/2 | n/a | n/a | both runs rewrote the whole file (1,699 tokens) instead of using the format |
| 50 | 0/2 | 1/2 | 1/2 | 1 of 50 (applying run) | 0/2 | other run: whole-file rewrite (3,195 tokens) |
| 100 | 1/2 (hit the 6,000-token cap) | 0/2 | 0/2 | n/a | n/a | one truncated whole-file rewrite; one reply echoed the placeholder text of the format spec |

Where edits applied (3 of 8 runs) they passed `ast.parse`, added 0 new ruff errors, changed 2 lines, did not touch the test file and passed the policy checks. But each fixed **one function only**. At no size did the model fix more than one defect per reply. So "edit applies" is not the limiting factor; the model's tendency to under-fix, and to ignore the format when asked for many changes, is. Multi-defect tasks should be split into one defect per call. At 100 changed lines the policy cap (`MAX_CHANGED_LINES` = 60) would reject the patch anyway.

### 3. Format comparison (10 independent small fixes in files of about 80 lines, same prompts otherwise)
| Format | Replies | Applies cleanly | Fix exactly correct | Test file touched | New ruff errors | `ast.parse` failures |
|---|---|---|---|---|---|---|
| Search/replace (`repair.edits`) | 10 | **10/10** | 7/10 | 1/10 | 2 (both from that test edit) | 0 |
| Unified diff (`git apply --check`, temp git repo) | 10 | **0/10** | 0/10 | 0/10 | none (none applied) | n/a |

All 10 diffs were rejected by git: 8 "corrupt patch", 1 "patch fragment without header", 1 "patch failed" (context did not match). `--recount` (ignores wrong hunk line counts) rescued none (0/10). One diff was a no-op (removed and re-added the same line). Of the 3 search/replace edits that applied but were not correct: one edited the test file instead of the source (and invented a new test), one also rewrote the docstring ("a invoice" to "an invoice"), one changed the line to `merged[key] += value` (wrong, raises KeyError). "Applies" does not mean "correct"; tests are still needed.

### 4. Quality per edit
Of the 13 edits that applied (3 from test 2, 10 from test 3), 13/13 parsed with `ast.parse`; the only new ruff errors (2) came from a model-authored test; 1/13 touched a test file (the policy would reject it). Changed lines per applying edit: 2 for single-line fixes, 4 for the docstring-rewrite case, 11 for the test-edit case.

### 5. Rate limits, latency, VRAM (local)
- Requests/min, tokens/min, retry-after: **none observed**; local Ollama has no rate limit. 0 failures and 0 retries in 37 live calls. **Cloud free-tier limits (RPM/TPM, 429 behaviour, retry-after) are NOT measured**: no keys, no cloud calls.
- Latency over the 37 live calls: p50 19.1 s, p95 284 s, max 1,018 s (the truncated 6,000-token reply). By prompt size: 1.5k tokens 21 s, 4k 45 s, 13k 197 s (prefill dominated, about 65 prompt tokens/s).
- End-to-end output speed: p50 10.3 tokens/s, p95 15.0 (includes prefill; calls with 20 or fewer output tokens excluded).
- VRAM (nvidia-smi sampled every 2 s): 5.0 to 5.7 GB already in use before each run (Ollama keeps the model resident); peak 5,855 MiB of 6,144. No out-of-memory events; the machine stayed responsive.

### Limits of this evidence
Single quantized 7B model on a partly CPU-offloaded setup; n=3 per read size and n=2 per write size, so any percentage has a very wide error bar (3 tries cannot separate 1/3 from 2/3). Synthetic code: template-generated, simple one-line bugs; the write task is N independent near-identical edits, which may be easier or harder than real multi-site fixes. At temperature 0 repeats are identical, so variants rather than repetitions were used. The 3,000/6,000-line reads and any context above 16,384 were not run. No Mistral/Devstral or other cloud results, so nothing here compares models. Rows were rescored from the gateway cache after a harness fix (test-file detection); latency and tokens are the original live values.

### Recommendations
- **D19 (edit format): search/replace.** On this model it applied 10/10 against 0/10 for unified diff. Keep exact-match, unambiguous-only apply and the policy (test files, size). Ask for one defect per call; treat "applies" as a precondition only, since the fix must still pass tests. Do not offer diff as a fallback for this model.
- **D20 (context budget, this model): at most about 4,000 prompt tokens (about 300 lines with numbering, about 16k characters) per prompt.** That is the largest size with a tolerable latency (about 45 s), and 13k tokens (about 200 s per call) showed no accuracy gain. Hard ceiling 16,384, which must be set via a Modelfile (the default 4,096 silently truncates). The current placeholder `agent_context_budget_chars` = 12000 (about 3k tokens) is consistent with this. Prefer the code map plus retrieved functions over whole files, because the model is not reliable at locating a line inside a big file.
- **D21 (primary model): undecided.** The evidence only shows local qwen2.5-coder:7b is usable for narrow single-edit tasks and weak for multi-line repairs (one defect fixed per reply at every size; 3 of 10 single fixes were wrong even when they applied). Cloud candidates (Devstral on Mistral, `:free` OpenRouter models) are untested, so no choice between them is justified. Keep local Qwen as the offline arm and repeat this script with a `:free` model before deciding D21.

## Part B addendum — Nemotron `:free` (EXPERIMENTAL ALTERNATIVE, not the planned model), format comparison only (2026-11-21)

Same 10 small fixes and scoring as the local run (`spikes/model_probe/probe.py --exp format`), provider OpenRouter, model `nvidia/nemotron-3-ultra-550b-a55b:free`, temperature 0. Raw results: `spikes/model_probe/results_openrouter_nemotron/`. 20 live calls, none failed, no rate limit hit.

| Model | Format | Applies cleanly | Fix exactly correct | Touched a test file | New ruff errors |
|---|---|---|---|---|---|
| qwen2.5-coder:7b (local, 16k ctx) | search/replace | 10/10 | 7/10 | 1 | 2 |
| qwen2.5-coder:7b (local, 16k ctx) | unified diff | 0/10 | 0/10 | 0 | 0 |
| nemotron-3-ultra :free (cloud) | search/replace | 10/10 | 10/10 | 0 | 0 |
| nemotron-3-ultra :free (cloud) | unified diff | 4/10 (8/10 with `--recount`) | 3/10 | 0 | 1 |

What this supports: **D19 stands**: search/replace applied cleanly 20/20 across both models; unified diff applied 4/20 without recount. It is a single small synthetic set (n=10 per cell), so it shows direction only.

Not run on the cloud model: read-limit and write-limit experiments (the free tier's daily request cap is unverified and those need many calls), so D20 rests on the local model only and **D21 (primary model) stays undecided**; the cloud model looks stronger on this one test but that is not a model comparison.

**Correction (2026-11-21):** the planned primary cloud model is Devstral (`devstral-small-latest`, provider `mistral`), not Nemotron. Nemotron was used only because it is free on OpenRouter. The Nemotron rows above are **not** Devstral results and must not be cited as such. Devstral probe runs are **NOT RUN**: OpenRouter lists only `mistralai/devstral-2512` at a paid price (no `:free` variant), so it cannot be used at $0 through that route. The probe script already supports `--provider mistral --model devstral-small-latest` (the gateway guard refuses providers not on the free allowlist until it is explicitly enabled). Run the same three experiments (read, write, format) on Devstral and on local Qwen with identical cases once free Devstral access is confirmed.
