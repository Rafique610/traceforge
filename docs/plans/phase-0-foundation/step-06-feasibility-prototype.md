# P0-S06 — Feasibility prototype: find the limits first

## A. Task identification
| Field | Value |
|---|---|
| Phase | 0 Foundation |
| Step | 6 |
| Task ID | P0-S06 |
| Synverk card | none (Synverk not used, D16) |
| Primary owner | Muhammad Rafique (Part A, retrieval spike) |
| Co-owner | Muhammad Ruhan Kamran (Part B, model probe) |
| Reviewer | optional |
| Priority | High (decides edit format, context budget, primary model) |
| Effort | 2 days each, in parallel |
| Status | IN PROGRESS (Part A done 21 Nov: see `docs/research/limits-report.md`; Part B not started) |
| Branch | `rafique/P0-S06-retrieval-spike`, `ruhan/P0-S06-model-probe` |

## B. Objective
Measure, with real numbers, where the approach breaks **before** building Phase 1 on assumptions: can simple search already find the cause, does a graph help when the cause is in another file, how much code each model can read and write reliably, and whether its edits apply. Output is a one-page limits report that feeds three decisions (D19–D21).

## C. Prerequisites
- P0-S02 merged (uv project and Taskfile exist).
- Part B: a Mistral API key in `.env` (`TRACEFORGE_MISTRAL_API_KEY`, through `Settings`), Ollama with `qwen2.5-coder:7b` pulled.
- `rg` (ripgrep) installed: `winget install BurntSushi.ripgrep.MSVC`.

## D. Technical background
- **Lexical vs ranked vs graph.** ripgrep finds exact matches with no ranking; BM25 ranks by term weight; a graph follows calls, imports and config reads. The spike checks whether the extra machinery earns its place on cases where the symptom and cause are in different files.
- **Code map.** A compact outline (file → classes/functions with signatures, no bodies) that tells the model what exists for a few hundred tokens.
- **Usable vs advertised context.** Models often lose accuracy well before their advertised window. We measure the point where locating a known bug stops working.
- **Search/replace edits.** The model returns "find these exact lines → replace with these" blocks; our code applies them. An edit whose old lines don't match the file exactly is invalid.
- The spike is **evidence gathering, not product code**: it lives in `spikes/`, is never imported by `backend/`, and its findings, not its code, carry forward.

## E. Implementation instructions
**Part A — Retrieval spike (Rafique), `spikes/retrieval/`**
1. A tiny app (3–5 files, ~300 lines) with 5 hand-made faults: 2 at distance 0 (bug on the trace line), 2 at distance 1 (config read in one file, crash in another), 1 at distance 2 (bug in a caller's caller).
2. One query per fault from the error message + traceback identifiers.
3. Rank files/functions four ways: **R0** ripgrep (hit count), **L** BM25 + trace anchor, **G** L + one/two-hop graph from `ast` calls/imports + config-key reads, **M** code map given to the model with "which function?" (optional, needs Part B's client).
4. Record Recall@1/@5 and time per query for each; note *why* each miss happened.

**Part B — Model probe (Ruhan), `spikes/model_probe/`**
1. **Read limit:** plant one known bug in Python files of 100, 300, 1k, 3k, 6k lines (real-looking code, not filler); ask for the file and line. 3 tries per size. Record accuracy per size.
2. **Write limit:** ask for fixes needing 5, 20, 50, 100 changed lines in search/replace format. Record truncation, format errors, and whether the edit applies.
3. **Format comparison:** same 10 small fixes as unified diff vs search/replace; record the share that apply cleanly.
4. **Code quality per edit:** parses (`ast.parse`), new ruff errors, lines changed, touched a test file (must be no).
5. **Free-tier limits:** requests/min, tokens/min, failures and retry-after values actually hit; latency p50/p95. From real calls only.
6. Run 1–5 on Mistral (pinned Devstral) and local Qwen2.5-Coder-7B; record hardware (GPU, VRAM) for local.

**Both**
7. Save raw results as JSON in `spikes/*/results/` and write `docs/research/limits-report.md`: one table per part, real numbers only, and a recommendation for D19 (edit format), D20 (context budget per prompt), D21 (primary model).

## F. Checklist
- [x] 5 hand-made faults with known distance (Part A)
- [x] R0, trace-only, L, G ranked and scored (Part A; M with a model deferred to Part B)
- [ ] Read-limit curve for both models (Part B)
- [ ] Write-limit and edit-validity numbers for both models (Part B)
- [ ] Diff vs search/replace comparison (Part B)
- [ ] Free-tier limits measured from real calls (Part B)
- [ ] Raw results saved; no invented numbers (Part A done: `spikes/retrieval/results/retrieval.json`)
- [ ] `docs/research/limits-report.md` written with recommendations (Part A written)
- [ ] D19–D21 updated from "provisional" to decided (or changed) in DECISIONS_AND_OPEN_QUESTIONS.md

## G. Expected deliverables
`spikes/retrieval/`, `spikes/model_probe/` (scripts + `results/*.json`), `docs/research/limits-report.md`, Taskfile entries `spike:retrieval`, `spike:probe`.

## H. Testing and validation
- Each script reruns from a clean clone with one task command and reproduces its JSON (LLM replies cached by prompt hash once P1-S05 exists; until then, store raw replies alongside results).
- Acceptance: the report answers, with numbers, (1) does ripgrep alone find distance-0 causes, (2) does the graph find distance-1/2 causes that ripgrep misses, (3) the largest file size each model locates bugs in reliably, (4) which edit format applies more often.

## I. Dependencies and integration
- **Depends on:** P0-S02.
- **Feeds:** P1-S05 (probe becomes the gateway's smoke test), P2-S02/P2-S03 (graph and baselines), P2-S04 (edit format, size cap), P1-S06 (context budget). If the report contradicts the plan, change the plan in the same PR as the report.

## J. Definition of done
Both parts run, the limits report exists with real numbers and three recommendations, and D19–D21 are confirmed or revised.
