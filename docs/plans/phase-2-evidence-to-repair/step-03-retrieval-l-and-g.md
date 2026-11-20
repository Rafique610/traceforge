# P2-S03 — Retrieval L and G, plus offline evaluation E1

## A. Task identification
| Field | Value |
|---|---|
| Phase | 2 Evidence-to-repair |
| Step | 3 |
| Task ID | P2-S03 |
| Synverk card | TRAC-14 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Normal (critical path) |
| Effort | 3 days |
| Status | NOT STARTED |
| Branch | `rafique/P2-S03-retrieval` |

## B. Objective
Produce the context the LLM sees, in two modes that differ **only** in graph features, under one token budget. This is the independent variable of the main research question, and E1 (retrieval quality without any LLM) is the free first R&D result for Assignment 3.

## C. Prerequisites
- P2-S01 (evidence anchors), P2-S02 (graph), P0-S05 (`ContextBundle`).
- `uv add rank-bm25` (assumption AS7) and a tokenizer for counting (`tiktoken` `cl100k_base` as an approximation; record that it's approximate).

## D. Technical background
- **Corpus:** one chunk per function/class (source lines), one per config key (declaration + read sites), one per test function. Chunk text includes path and qualname.
- **Query:** error messages, exception types, identifiers in log lines, trace frame function names, service name.
- **Shared by both modes:** BM25 candidate generation (top 50) **and traceback anchoring**: force-include the top in-repo trace frame's symbol and any config key literally named in evidence (design fix D10).
- **G only:** graph proximity `1/(1+d)` from anchors; ≤2-hop expansion adds neighbours not in the BM25 top 50; config-key binding links a named key to its `READS_CONFIG` functions; penalty for paths through `unknown:` edges.
- **Score (initial, from the architecture doc; tune on dev only after P3-S01's freeze):**
  L: `score = lex_norm + anchor_bonus`; G: `score = 0.30·lex + 0.25·anchor + 0.20·graph_proximity + 0.10·test_link − 0.10·uncertain`. (The semantic term from the proposal is disabled in both arms for A3.)
- **Budget:** the same `token_budget` for L and G; about 20% reserved for the agent's own `read_symbol` calls. Dedupe overlapping spans.
- **Metrics:** Recall@5 (any gold symbol/key in top 5), MRR (first gold hit), nDCG@10, tokens used, all by `distance` bucket (0, 1, 2+).

## E. Implementation instructions
1. **`retrieval/corpus.py`:** build chunks from the graph (spans) and source; cache per `base_sha`.
2. **`retrieval/lexical.py`:** tokenizer (split identifiers on `_`/camelCase), BM25 index, `candidates(query, k=50)`.
3. **`retrieval/anchors.py`:** from `EvidenceBundle`: trace frames → `symbol_at()`; config keys named in log/config items → `cfg:` nodes.
4. **`retrieval/graph_ranker.py`:** proximity, expansion, binding, uncertainty penalty.
5. **`retrieval/context_budget.py`:** pack top hits into `token_budget` (largest-score-first, dedupe), excerpt with line numbers, `reasons` (e.g. `["bm25:0.71","anchor:trace","graph:d=1 via READS_CONFIG"]`).
6. **`retrieval/retrieve.py`:** `retrieve(evidence, graph, mode, token_budget) -> ContextBundle`.
7. **`retrieval/e1.py` + `task eval:retrieval SPLIT=dev`:** for each manifest case, collect evidence (or load cached bundle), run both modes, compute metrics against `gold_symbols`/`gold_config_keys`, print the table by distance, save JSON to `runs/e1/<split>-<timestamp>.json`.
8. **Fairness test:** with graph features zeroed, G must equal L exactly (same candidates, same budget, same order).
9. Unit tests for tokenizer, anchors, packing (never exceeds budget), metric functions (shared with P3-S02 or imported from there once it exists).

Edge cases: no trace and no named key → anchors empty; G falls back to lexical + nothing (the result is still valid). Gold symbol not in corpus (e.g. Compose-only fault) → gold matches a `ComposeEnv`/config node.

**Additions from the feasibility review (21 Nov 2026; see D18–D24)**
- Add baseline **R0 ripgrep**: same query terms, files ranked by hit count. Optional **E embeddings** (small local model via Ollama) if time allows. Report all arms in E1 with Recall@5, MRR, nDCG@10 and time per query (D18).
- Add a **trace-only** reference (context = traceback files only) to show how much any retrieval adds.
- The code map is given identically to L and G, so it never decides the L-vs-G comparison (D22).

## F. Checklist
- [ ] Chunk corpus per SHA
- [ ] BM25 candidates with identifier-aware tokenizer
- [ ] Anchors from evidence (both modes)
- [ ] Graph ranker (G only)
- [ ] Budget packing with reasons and excerpts
- [ ] `retrieve()` returns valid `ContextBundle`
- [ ] E1 CLI with per-distance table and saved JSON
- [ ] Fairness test (G with graph off == L)
- [ ] Unit tests
- [ ] E1 table for seed cases pasted on TRAC-14
- [ ] Weights left at initial values (tuning only after freeze, on dev)
- [ ] R0 ripgrep baseline in E1
- [ ] Trace-only reference in E1
- [ ] Embeddings arm (optional) or explicitly dropped

## G. Expected deliverables
New: `backend/traceforge/retrieval/{corpus,lexical,anchors,graph_ranker,context_budget,retrieve,e1}.py`, tests. Modified: `pyproject.toml`, `Taskfile.yml`, `README.md`. Interface: `retrieve(...) -> ContextBundle`.

## H. Testing and validation
- Fairness test passes; packing never exceeds budget.
- E1 runs on the 4 seed cases and prints the table (small n is expected; it's a pipeline check).
- Acceptance: identical inputs → identical bundles (determinism test).

## I. Dependencies and integration
- **Informed by:** P0-S06 limits report.
- **Depends on:** P2-S01, P2-S02.
- **Unblocks:** P2-S07 (real context), P4-S01 (E1 on the full set), P5-S03.
- **Integration:** Ruhan's `ContextSource` gets `RetrievalContextSource(mode)` at Sync 2; the condition's L/G letter selects the mode.

## J. Definition of done
Merged after Ruhan's review; fairness and determinism tests pass; E1 runs; TRAC-14 approved.
