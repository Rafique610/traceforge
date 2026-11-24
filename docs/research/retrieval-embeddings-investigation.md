# Retrieval and embeddings investigation (read-only, from code and saved artifacts)

Scope: backend `D:\TraceForge\repo\backend\traceforge`, conditions L0/G0/L1/G1 (L = lexical arm, G = graph arm; 0/1 = feedback off/on). Frozen results under `results/final/` were only read. Scoring script (not in repo): `C:\Users\RUHAN\AppData\Local\Temp\claude\7d1aaa8a2e53eb4c\1ff1b896-ce15-4824-bbbe-865f5ebc8bb5\scratchpad\score_retrieval.py` (writes `scores.json` beside it).

## Findings

1. No vector embeddings exist anywhere in the pipeline: no embed/vector/faiss/chroma/pgvector/sentence-transformers code, no vector column in migrations, plain `postgres:16` image, no such dependency in `pyproject.toml`. Embeddings were only ever an "optional E arm" in plans (docs/plans/phase-2-evidence-to-repair/step-03-retrieval-l-and-g.md:49,67; DECISIONS D18).
2. L = BM25 (rank-bm25 Okapi, k1=1.5, b=0.75) over graph-derived chunks with an identifier-aware tokenizer. G = the same candidate pool, BM25 and anchors, plus graph proximity (<=2 hops), test link, uncertainty penalty, graph expansion and symptom graph anchors. Both pack into the same token budget with the same packer.
3. Offline, 35 cases, replicate 0: gold (symbol or config key) is in the context actually sent in 23/29 cases for L and 24/29 for G (6 cases have no gold symbols/keys: 3 runtime_dependency, 3 insufficient_evidence). Mean gold recall in sent context 0.69 (L) vs 0.72 (G); MRR 0.14 vs 0.23; precision (sent chunks overlapping gold) 0.039 vs 0.058; mean context about 2336 vs 1712 tokens.
4. The weak spot is configuration cases: gold recall in sent context is 0.33 for both arms (6/9), yet 8/9 (L) and 9/9 (G) were diagnosed at the exact key. The agent recovers through shared non-retrieval tools (code map, `read_symbol`, `search_code`, `get_neighbors`), so retrieval quality is only weakly coupled to final diagnosis. Where gold was not sent, 5/6 (L) and 5/5 (G) were still diagnosed exactly; only L on shop_api-019 failed.
5. Retrieval latency is not recorded per arm in the saved artifacts (only whole-run timings), so it cannot be reported from artifacts.
6. Free local embedding option found on disk: Ollama 0.40.17 is installed and `all-minilm:22m` is in its model store (manifest file present). The Ollama server did not respond to `ollama list` (timed out), so runtime availability is NOT confirmed. The backend venv has numpy and rank_bm25 but no torch/sentence-transformers/onnx/faiss/sklearn (checked by listing `.venv\Lib\site-packages`; the venv has no pip, so `pip list` was not possible).

## A. Are embeddings used?

No.
- `grep -rniE "embed|sentence_transformers|faiss|chroma|pgvector|vector|cosine|dimension"` over `backend/traceforge`, `backend/alembic`, `backend/pyproject.toml`, `compose*.yaml`, `lab`, `scripts` returned only `traceforge/evaluation/metrics/retrieval.py:61` and `metrics/__init__.py:8,28,33`, where "dimension" means case-level breakdown dimensions (unrelated).
- Migrations `alembic/versions/0001_incidents.py` and `0002_patches_validation_reviews.py`: no vector type. DB image is `postgres:16` (`compose.yaml:5`, `compose.prod.yaml:6`), which has no pgvector.
- Dependencies (`backend/pyproject.toml:6-17`): networkx, openai, psycopg, rank-bm25, sqlalchemy and others. The `openai` SDK is used only for `client.chat.completions.create` (`agent/gateway.py:138,184,226`); no embeddings endpoint call.
- Only mentions are planning docs: step-03 plan line 49 ("Optional E embeddings (small local model via Ollama) if time allows"), line 67 ("Embeddings arm (optional) or explicitly dropped"), `docs/plans/DECISIONS_AND_OPEN_QUESTIONS.md:28` (D18).
- Hence no model, provider, dimension, storage or evaluation condition for embeddings exists.

## B. Mechanisms in the L and G arms

Call path: `agent/pipeline.py:168` `src.context.retrieve(evidence, None, condition[0], budget // 4)` with `budget = agent_context_budget_chars` = 12000 (`config.py:72`; fallback `agent/prompting.py:16`), so token_budget = 3000. `RealContextSource.retrieve` (`retrieval/sources.py:39-43`) -> `retrieval/retrieve.py:183 retrieve` -> `build_query` (`retrieval/anchors.py:260`) -> `rank` (`retrieve.py:101`) -> `context_budget.pack` (`retrieval/context_budget.py:257`). The first letter of the condition selects the arm; the feedback digit does not enter retrieval.

| Aspect | L arm | G arm | Evidence |
|---|---|---|---|
| Corpus | one chunk per function/method/class header (max 12 lines), test function, config key, class-level field | same | `corpus.py:163-209`; BM25 text capped at 6000 chars `corpus.py:22` |
| Lexical scorer | BM25Okapi, query terms de-duplicated, scores normalised by max, top `TOP_K=50` with score>0, ties by hit_id | same | `lexical.py:1,32-54`; `retrieve.py:85` |
| Tokeniser | split on `_`, camelCase, digits, lowercased; split identifiers also kept whole; stop-words and length<=1 dropped | same | `lexical.py:9-23` |
| Query | service name + signal lines of log/health/trace/issue evidence (error/exception/fail/timeout regex, max 40 lines, FINDING hints) + qualnames of trace frames + symptom terms (endpoint words, assertion identifiers, failing test names, boilerplate removed) | same terms | `anchors.py:94-113,142-160,278` |
| Anchors | innermost 2 project trace frames forced; other frames strength 0.5; config keys literally named in log/trace/health/issue evidence forced, max 3 | same, plus graph-only symptom anchors: functions covered by failing tests (`tests_covers`, strength 0.6 x share of failing tests, max 8), route handlers (0.8), up to 6 settings read by anchored code (0.5, not forced, not walked) | `anchors.py:20-21,43-48,116-129,177-257`; `retrieve.py:118-124` |
| Graph use | none | Dijkstra walk from each anchor over calls, reads_config, declares_config, service_env, service_runs, depends_on, tests_covers; MAX_HOPS=2; cost = sum 1/(edge weight x confidence); hubs down-weighted; key<->settings-field binding costs no hop; proximity = strength/(1+cost) | `graph_ranker.py:297-424` |
| Expansion | none | <=2-hop neighbours not in BM25 top-50 join the pool | `retrieve.py:132-135` |
| Score | 0.30 lex + 0.25 anchor | 0.30 lex + 0.25 anchor + 0.20 prox + 0.10 test_link - 0.10 uncertain | `retrieve.py:89-98,145-151` |
| Ordering | forced anchors first (anchor order), then -score, hit_id | same | `retrieve.py:170-180` |
| Budget cut | pack: usable = 80% of token_budget (20% reserved for agent reads), cost = header + excerpt chars/4, overlapping lines de-duplicated, excerpt max 80 lines, truncate to fit, skip if no room | same | `context_budget.py:214-288` |
| Render into prompt | hits sorted by score desc, hidden paths dropped, cut at 12000 chars | same | `agent/prompting.py:39-56` |

Shared between arms: corpus, tokeniser, BM25 index, query terms (including symptom terms), trace and config-key anchors, packer, render budget, and the agent tools and code map (`sources.py:98-157`: `workspace_index`, `search_code`, `read_symbol`, `neighbors`, `code_map`, identical in all conditions, D22). Differences are only the G graph features (`GraphFeatures` all on by default, `graph_ranker.py:312-335`): symptom graph anchors, expansion, and the proximity/test-link/uncertainty score terms. `search_code` is a name/docstring token-overlap scorer (`sources.py:115-132`).

Artifact semantics: `retrieval.json` holds both L and G lists from `compare(..., 3000)` (`evaluation/real_run.py:282`; `retrieval/compare.py`); `context_sent.json` holds the chunks actually rendered for the run's own arm (`real_run.py:332`). The "retrieved" list equals the packed hits at the 3000-token budget, not the raw BM25 top-50.

## C. Offline retrieval quality (35 cases, r0, final-axforge-L0 vs -G0)

Method: gold from `datasets/manifests/test.json` (`gold_symbols` path+qualname+lines, `gold_config_keys`, service-qualified), used only for scoring. "Retrieved" = ids in `retrieval.json[arm]`, exact id match (`sym:path::qualname`, `cfg:svc.KEY`). "Sent" = `context_sent.json` hits, matched by id or line overlap with a gold symbol span. Recall = fraction of gold items found; "any" = at least one found. MRR = 1/rank of first gold hit in the list (0 if none). Precision = fraction of sent chunks overlapping gold; file-precision = fraction in a gold file. Tokens = rendered chars / 4 (the packer's own estimate). Cases with empty gold (runtime_dependency, insufficient_evidence) are excluded from recall/MRR/precision.

Overall (29 cases with gold; chunk/char/token means over all 35):

| Arm | any in retrieved | any in sent | recall retr. | recall sent | MRR retr. | MRR sent | precision sent | file-precision sent | chunks sent | chars sent | tokens sent | exact diagnosis (of 29) | class correct (of 35) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L | 21 | 23 | 0.655 | 0.690 | 0.123 | 0.137 | 0.039 | 0.123 | 22.1 | 9345 | 2336 | 28 | 32 |
| G | 23 | 24 | 0.707 | 0.724 | 0.194 | 0.226 | 0.058 | 0.139 | 16.6 | 6849 | 1712 | 29 | 35 |

"Sent" can exceed "retrieved" because line overlap also credits an enclosing or adjacent chunk.

By cause class:

| Class | n | Arm | any retr. | any sent | recall sent | MRR sent | precision sent | exact diag | class correct | mean tokens sent |
|---|---|---|---|---|---|---|---|---|---|---|
| application_code | 20 | L | 17 | 17 | 0.85 | 0.166 | 0.037 | 20 | 20 | 2339 |
| application_code | 20 | G | 18 | 18 | 0.90 | 0.236 | 0.055 | 20 | 20 | 1601 |
| configuration | 9 | L | 4 | 6 | 0.333 | 0.073 | 0.043 | 8 | 8 | 2340 |
| configuration | 9 | G | 5 | 6 | 0.333 | 0.203 | 0.064 | 9 | 9 | 1652 |
| runtime_dependency (no gold symbol) | 3 | L / G | n/a | n/a | n/a | n/a | n/a | 0 / 0 | 1 / 3 | 2312 / 2020 |
| insufficient_evidence (no gold) | 3 | L / G | n/a | n/a | n/a | n/a | n/a | 0 / 0 | 3 / 3 | 2330 / 2330 |

Cases where the gold region was NOT in the context sent:

| Arm | Case | Class | Gold in retrieved list? | Diagnosis |
|---|---|---|---|---|
| L | shop_api-008 | application_code | no | exact (`lab/worker/retry.py::with_backoff`) |
| L | shop_api-019 | configuration | no | wrong class, no target (the only miss that failed) |
| L | shop_api-148 | configuration | no | exact (`shop_api.SHIPPING_FEE`) |
| L | shop_api-172 | application_code | no | exact (`quote`) |
| L | shop_api-115 | application_code | no | exact (`can_fulfil`) |
| L | shop_api-057 | configuration | no | exact (`TAX_RATE`) |
| G | shop_api-019 | configuration | no | exact (`COUPONS_VALID_UNTIL`) |
| G | shop_api-148 | configuration | no | exact |
| G | shop_api-115 | application_code | no | exact |
| G | shop_api-035 | application_code | no | exact (`dead_letter`) |
| G | shop_api-057 | configuration | no | exact |

No case had gold in the retrieved list but dropped before send, and no case had gold sent yet a non-exact diagnosis. Retrieval is therefore not the binding constraint in the frozen experiment: the shared tools and symptom/evidence carry most of the localisation. G adds one exact diagnosis (shop_api-019) and 3 more correct classes (2 runtime_dependency, 1 configuration) and sends about 27% fewer tokens, but both arms have very low precision (4-6%): 16-22 chunks sent, about one of them gold.

Caveats: small n, replicate 0 only; MRR uses raw list order (forced anchors first). Retrieval latency is not stored per arm (`run_meta.json` has only whole-run `timings`, merging evidence collection and retrieval) and was not computed. Config-key chunks are matched by id only (no line overlap), which can make configuration "retrieved" recall differ from "sent".

## D. Design: hybrid retrieval evaluation (design only, not run)

Principles: no contamination of frozen L0/G0/L1/G1; no LLM in stage 1; gold used only by offline scorers.

1. Conditions and isolation. New arms: `E` (embeddings only) and `H` (BM25 + graph + embeddings fused); condition names `H0`/`H1` only if a later LLM stage is approved. Do not reuse L/G (`condition[0]` selects the arm at `pipeline.py:168`). Implement in a new module (e.g. `retrieval/hybrid.py`) leaving `rank()` untouched, keep the existing fairness property (all graph features off => G == L) under test. Outputs go to new dirs (e.g. `runs/retrieval-bench/<run_id>/`, `results/hybrid/`), never `results/final/`. Record code fingerprint and manifest sha256 as `retrieval/e1.py` does.
2. Stage 1: offline retrieval-only benchmark on the DEV split (33 cases: 16 configuration, 15 application_code, 1 runtime_dependency, 1 insufficient_evidence), using the existing E1 harness (`retrieval/e1.py`; `Taskfile.yml:183` `eval:retrieval SPLIT=dev`) extended with the new arms beside R0, trace-only, L and G. E1 needs saved evidence bundles per case and lists cases without one as skipped; collecting dev bundles needs the faulty lab (an effort risk). The test split (151) and the frozen 35 stay untouched until hypotheses are fixed.
3. Fusion. Reciprocal rank fusion `score = sum_r 1/(k + rank_r)` over three ranked lists (BM25 top-50, the G ranking, embedding top-50), forced anchors kept first as today, same packer and the same 3000-token budget so arms are comparable. Variants fixed in advance (k in {30, 60}), one run each, no tuning loops.
4. Metrics: Recall@1/5/10, MRR, nDCG@10 (existing `evaluation/metrics/retrieval.py`), precision of packed chunks, gold-in-packed-context, tokens/chars packed, query latency and index build time, split by cause class (configuration, recall 0.33 in frozen runs, is the primary target).
5. Determinism: local embeddings with fixed model tag, quantisation and batch size; fixed seed for any tie-breaking, ties by hit_id; store a vector hash per chunk.
6. Preregistered hypotheses (commit before running):
   - H1: H raises gold-in-packed-context recall on dev configuration cases over G by >= 0.15 absolute (frozen reference 0.33).
   - H2: H does not lose recall on application_code vs G (non-inferiority margin 0.05).
   - H3: at equal token budget H precision >= G (frozen reference 0.058).
   - H4 (sanity): E alone is worse than BM25 on identifier-heavy queries.
   Decision rule: only if H1 and H2 hold on dev is an LLM stage (H0 on a selection with replicates as in the frozen design) proposed; no peeking at test metrics.
7. Embedding model candidates (free, local). Verified: Ollama 0.40.17 installed and `all-minilm:22m` present in its model store (384-dim general-text model; server not responding to `ollama list`, so runtime availability unconfirmed). Not verified/not installed: `nomic-embed-text`, `bge-small` (would need a pull); sentence-transformers needs torch, absent from the backend venv (system Python has numpy 2.3.5 and scikit-learn 1.7.2, not in the project venv). Installing or pulling anything is a separate decision. Prefer to compare at least one code-aware model, since all-minilm is general text.
8. Cost estimate. Dev effort about 3-5 days: hybrid module 1 day; embedding index builder plus cache keyed like `get_corpus` 0.5 day; extend E1 and scorer 1 day; dev evidence bundles 0.5-1 day; analysis and write-up 1 day. Tokens: stage 1 uses 0 LLM tokens. Embedding compute: chunks are at most 6000 chars (~1500 tokens), a few hundred chunks per case tree, so roughly 0.5-1M embedding tokens over 33 dev cases on local CPU (estimate, not measured), free. A later LLM stage would repeat the frozen cost (about 40k tokens in per case per run, e.g. shop_api-008 L0 `run_meta.json`) times cases x conditions.
9. Risks.
   - Leakage: never embed test-split files, hidden tests or fault-generator artefacts (`datasets/cases/*/mutation.patch`); embed only the tree the agent could see, with the same `_FORBIDDEN_PARTS` (`sources.py:19`) and hidden-path filter (`prompting.py:12`). Gold and symptom-audit terms stay in the offline scorer. Do not use test manifests to select k, model or weights.
   - Index staleness: the corpus is cached per (repo, base_sha, content_hash) (`corpus.py:215`); the embedding cache must use the same key or a mutated case reuses another case's vectors.
   - Context budget: fusion must not raise packed tokens; keep the 3000-token budget and 80% usable fraction and report tokens, so gains are not just more context (G already sends fewer tokens than L).
   - Query fairness: use the same query text as BM25 (service + signal lines + frame names + symptom terms); LLM query rewriting would add an LLM stage and confound.
   - Small dev n (33; 1 runtime_dependency, 1 insufficient_evidence): report paired case-level differences with bootstrap intervals and avoid class claims beyond configuration and application_code.
   - Ceiling effect: frozen exact diagnosis is already 28-29/29 with imperfect retrieval, so retrieval gains may not move diagnosis; state in advance that stage 1 measures retrieval only.
