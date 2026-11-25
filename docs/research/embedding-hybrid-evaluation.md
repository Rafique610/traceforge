# Embedding retrieval and hybrid fusion: evaluation (P5-S08)

Status: results of a preregistered, retrieval-level offline evaluation. Task owner Rafique (reviewer); executed by Ruhan's session at the project owner's direction. Zero LLM / provider calls (`llm_or_provider_calls: 0` in every run), zero AxForge / BeatAPI; embeddings came from the local Ollama server only. This is retrieval evidence only: it says nothing about diagnosis or repair and makes no claim about G1. Gold labels are used only by the scorer. ADR 0003 stays PROPOSED; the decision field is left to the owner.

Preregistration (written before any embedding-arm run): [embedding-hybrid-preregistration.md](embedding-hybrid-preregistration.md), SHA-256 `8f295f02cf86a13681beeb2d4f7ac84b7613106c8ee118bf68f82ff69a919c72`. Nothing was committed by this session before the runs, so the hash is the timestamp-independent anchor.

## 1. Headline

- **Preregistered verdict: NO-GO for embeddings in the retrieval path.** H1 FAIL, H2 FAIL, H3 FAIL, H4 PASS (primary model jina-code, both RRF k). Go needed H1 and H2.
- On the 31 scored dev cases, the existing G arm beats every embedding arm on the metrics that matter for the packed context: gold coverage in the packed context, Recall@10, nDCG@10 (G minus RET-LGE: coverage +0.113 [+0.032, +0.226], Recall@10 +0.290 [+0.113, +0.468]). Adding embeddings to G lowered coverage on both dev cause classes.
- Embeddings alone (RET-E) are clearly worse than G on dev (coverage 0.581 vs 0.919) and than BM25 on exact-identifier queries (MRR 0.384 vs 0.746).
- A niche exists, and it is small and uncertain: on the 45 free-text benchmark queries the fused arms are nominally ahead of G (RET-LE jina k=30: Recall@10 0.607 vs 0.556, packed coverage 0.693 vs 0.622), but the intervals include zero, and the gain sits in `paraphrased_bug` and `symptom_no_identifier` queries (n = 6 each) where BM25 finds almost nothing. That niche is absent in the real pipeline's inputs, where the symptom carries identifiers and trace anchors.
- Cost is small in absolute terms (about 15 to 25 ms per query embedding at idle, 1 to 6 s per 100 chunks, under 1 MB of vectors per 280-chunk tree) but non-zero and adds a running model server dependency.

## 2. Models: compatibility and measured facts

Local Ollama 0.40.17, Windows 11, GPU GTX 1660 SUPER (6 GiB), CPU Ryzen 5 2600. Models present at the start: `all-minilm:22m` (plus three chat models). C: free space 1.9 GB before the pulls, 1.4 GB after both pulls, 1.1 GB at the end (other work on the machine also writes there). Pull limits were respected: two pulls, 596 MB total (limits: < 350 MB each, < 600 MB total, > 1.0 GB free).

| Tag | Model (Ollama) | Pull size | Params | Dims | Context (model / loaded by Ollama) | Resident in Ollama (`ollama ps`) | Digest | Result |
|---|---|---|---|---|---|---|---|---|
| minilm | `all-minilm:22m` (general baseline) | 45 MB (already local) | 23M | 384 | 512 / 256 | 27 MB, 100% GPU | `1b226e2802db` | works |
| nomic | `nomic-embed-text` | 274 MB | 137M | 768 | 2048 / 2048 | 335 MB, 100% GPU | `0a109f422b47` | works; uses `search_query:` / `search_document:` prefixes |
| jina | `unclemusclez/jina-embeddings-v2-base-code` (community build of jina-embeddings-v2-base-code, F16) | 322 MB | 160M | 768 | 8192 / 4096 | 336 MB, 100% GPU | `9fe680d4d58b` | works (primary model) |

All three return unit-norm finite vectors and identical vectors on repeat calls (max abs diff 0.0). Compatibility failures: none at model level. One run failure: the first `nomic` harness run crashed once with `HTTP 400 Bad Request` from `/api/embed` during the first sync (log kept in `results/retrieval/p5s08-analysis/run_nomic_attempt1_crash.log`); re-embedding the same texts by hand then succeeded and the run was repeated unchanged (a preregistered crash repair, not a tuning re-run). The cause was not identified (the Ollama server may have been busy with other work at the time; not confirmed). A model with a code-specific build was not available under an official name: the jina build is a community upload (`unclemusclez/`), CodeRankEmbed was not tried.

Timings. Two sets exist and must not be confused. The harness runs used the default `http://localhost:11434` base URL; on this machine each HTTP call then pays about 2.0 s of name-resolution delay (IPv6 first), which inflates every harness latency and index time. The microbenchmark `results/retrieval/p5s08-analysis/latency_microbench.py` (output in `latency_microbench.txt`, run at idle after the evaluation) measures both:

| Model | one query embed, `localhost` | one query embed, `127.0.0.1` | 100 lab chunks, 4 batches of 32, `127.0.0.1` |
|---|---|---|---|
| minilm | 2037 ms | 15 ms | 1.2 s |
| jina | 2053 ms | 25 ms | 5.7 s |
| nomic | 2055 ms | 25 ms | 5.8 s |

The 100-chunk figures are on the GPU (Ollama reports 100% GPU); no CPU-only timing was taken. The harness `latency_ms` columns for dense arms (about 2050 to 2200 ms) therefore measure the resolution delay, not the models; use the table above. BM25 / G latency is 3 to 15 ms per query. Bug to fix before any adoption (not edited here, `traceforge/index` is outside this task's ownership): `OllamaEmbedder` should default to `127.0.0.1`.

**Selection.** minilm (general baseline) and jina (code-trained, primary, fixed in the preregistration) are the evaluated models for the verdict; nomic is exploratory and reported but not eligible. All three were run.

## 3. What was run

| Item | Value |
|---|---|
| Arms | RET-L, RET-G (= RET-LG, test-verified identical), RET-E, RET-LE (= ablation L+E), RET-LGE (= ablation G+E), per model, RRF k in {30, 60} |
| Fusion | forced anchors first (as in L/G), then RRF over the base top 50 and the dense top 50; ties by best rank in the base list then chunk id |
| Dense | cosine, flat numpy, `traceforge.index` incremental namespace per repo; the whole dev split shares one namespace (31 mutated trees of one lab: only changed chunks are embedded); query = the exact BM25 string, no rewrite |
| Budget | 3000 tokens (2400 usable) through the shared `pack()`; extra null at 4500 (L, G, RET-LGE jina k=60) |
| Data | 45 benchmark queries (3 repos) and the dev split: **31 of 33 cases scored** (2 skipped: `shop_api-003` runtime_dependency and `shop_api-004` insufficient_evidence, no retrieval target). The 19 missing evidence bundles were collected locally with `lab_collect` (zero tokens, no secret leak, contract valid); the earlier harness run scored 12 |
| Runs | one run per model (`p5s08-jina`, `-minilm`, `-nomic`), one null run (`p5s08-null4500`), analysis `p5s08-analysis` (`analysis.md` has every table, `analysis.json`, `build_log.jsonl`) |

## 4. Preregistered hypotheses (primary model: jina)

Pass = point estimate meets the threshold at both k. 95% CI = paired bootstrap, 10,000 resamples.

| H | Test | G (baseline) | Diff k=30 [CI] | k=30 | Diff k=60 [CI] | k=60 | Holds |
|---|---|---|---|---|---|---|---|
| H1 | dev configuration (n=16): packed gold coverage, RET-LGE minus G >= +0.15 | 0.906 | -0.094 [-0.188, +0.000] | FAIL | -0.094 [-0.188, +0.000] | FAIL | **FAIL** (ceiling also: G is already 0.906) |
| H2 | dev application_code (n=15): coverage, G minus RET-LGE <= 0.05 | 0.933 | -0.133 [-0.333, +0.000] (loss 0.133) | FAIL | -0.133 [-0.333, +0.000] | FAIL | **FAIL** |
| H3 | dev (n=31): packed precision, RET-LGE minus G >= 0 | 0.058 | -0.004 [-0.010, +0.002] | FAIL | -0.003 [-0.009, +0.002] | FAIL | **FAIL** (differences are tiny; packed precision is about 6% for every arm because the packer fills the budget) |
| H3b (suppl.) | 45 queries: packed precision, RET-LGE minus G | 0.080 | +0.002 [-0.011, +0.016] | PASS | -0.000 [-0.013, +0.013] | FAIL | FAIL (no difference) |
| H4 | exact_identifier (n=10): MRR of RET-E minus BM25 (RET-L) < 0 | L 0.746 | E 0.384: -0.362 [-0.618, -0.120] (R@5 -0.150 [-0.500, +0.200]) | PASS | same (E has no k) | - | **PASS** (CI excludes 0) |

Decision rule: H1 and H2 both fail, so **NO-GO**. The same sign holds for the other models (section 7 and `analysis.md`): minilm fused minus G on dev configuration coverage -0.156 [-0.281, -0.062]; nomic -0.125 [-0.250, -0.031]; application_code coverage 0.000 for minilm, -0.133 for nomic. No model/arm combination reached +0.15.

## 5. Direct comparisons

Means (31 dev cases; 45 repo queries). Tokens used are 2390 to 2395 for every arm (equal budget).

| Arm | repos R@10 | repos MRR | repos nDCG@10 | repos file@1 | repos packed cov | dev R@10 | dev MRR | dev nDCG@10 | dev file@1 | dev packed cov | dev packed prec |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **G** (existing best) | 0.556 | 0.397 | 0.400 | 0.489 | 0.622 | 0.839 | 0.390 | 0.479 | 0.226 | 0.919 | 0.058 |
| L (BM25 + anchors) | 0.556 | 0.393 | 0.398 | 0.489 | 0.622 | 0.790 | 0.306 | 0.411 | 0.226 | 0.919 | 0.061 |
| **G+E (RET-LGE jina k=60)** | 0.606 | 0.429 | 0.416 | 0.400 | 0.681 | 0.548 | 0.343 | 0.368 | 0.226 | 0.806 | 0.055 |
| RET-LGE minilm k=60 | 0.544 | 0.427 | 0.403 | 0.444 | 0.646 | 0.726 | 0.355 | 0.413 | 0.226 | 0.839 | 0.059 |
| RET-LGE nomic k=60 | 0.598 | 0.424 | 0.416 | 0.511 | 0.665 | 0.661 | 0.334 | 0.391 | 0.226 | 0.790 | 0.059 |
| **E alone (RET-E jina)** | 0.491 | 0.383 | 0.346 | 0.400 | 0.637 | 0.468 | 0.312 | 0.323 | 0.226 | 0.581 | 0.038 |
| RET-E minilm | 0.528 | 0.383 | 0.361 | 0.422 | 0.631 | 0.532 | 0.284 | 0.315 | 0.194 | 0.581 | 0.046 |
| RET-E nomic | 0.513 | 0.449 | 0.401 | 0.511 | 0.644 | 0.516 | 0.284 | 0.309 | 0.194 | 0.532 | 0.043 |
| **Best hybrid** (rule: lowest mean rank over R@10, MRR, nDCG, coverage on repos and dev) = RET-LE jina k=30 | 0.607 | 0.430 | 0.418 | 0.400 | 0.693 | 0.500 | 0.345 | 0.351 | 0.258 | 0.839 | 0.056 |

On the repos RET-LE and RET-LGE are identical (G equals L on free-text queries without anchors; the same was true in P5-S06).

Paired differences, primary model (A minus B, 95% CI):

| Slice | G - RET-LGE: coverage | G - RET-LGE: R@10 | G - RET-E: coverage | RET-LGE - RET-E: coverage | best hybrid - G: R@10 | best hybrid - G: coverage |
|---|---|---|---|---|---|---|
| 45 queries | -0.059 [-0.144, +0.020] | -0.050 [-0.144, +0.037] | -0.015 [-0.144, +0.117] | +0.044 [-0.044, +0.141] | +0.052 [-0.033, +0.143] | +0.070 [-0.013, +0.157] |
| dev (31) | +0.113 [+0.032, +0.226] | +0.290 [+0.113, +0.468] | +0.339 [+0.194, +0.500] | +0.226 [+0.097, +0.371] | -0.339 [-0.500, -0.194] | -0.081 [-0.210, +0.032] |
| dev configuration (16) | +0.094 [+0.000, +0.188] | +0.125 [+0.031, +0.250] | +0.156 [+0.062, +0.281] | +0.062 [+0.000, +0.156] | -0.156 [-0.281, -0.062] | -0.094 [-0.188, +0.000] |
| dev application_code (15) | +0.133 [+0.000, +0.333] | +0.467 [+0.133, +0.733] | +0.533 [+0.267, +0.800] | +0.400 [+0.200, +0.667] | -0.533 [-0.800, -0.267] | -0.067 [-0.267, +0.133] |

Reading: on dev, G is better than G+E and E alone; the fusion rescues part of what E alone loses (RET-LGE minus RET-E coverage is positive), but never recovers G. On the 45 queries no pairwise difference excludes zero except that fusion beats E alone on Recall@10 and nDCG@10 (RET-LGE minus RET-E R@10 +0.115 [+0.019, +0.219]).

### Per query type (45 queries, jina; RET-LE = RET-LGE here)

| Type | n | BM25 (L) R@10 / MRR | E R@10 / MRR | RET-LE k=60 R@10 / MRR |
|---|---|---|---|---|
| exact_identifier | 10 | 1.000 / 0.746 | 0.750 / 0.384 | 1.000 / 0.583 |
| paraphrased_bug | 6 | 0.417 / 0.312 | 0.667 / 0.632 | 0.750 / 0.611 |
| symptom_no_identifier | 6 | 0.056 / 0.048 | 0.444 / 0.323 | 0.361 / 0.310 |
| indirect_dependency | 7 | 0.548 / 0.212 | 0.190 / 0.139 | 0.405 / 0.256 |
| configuration | 10 | 0.567 / 0.366 | 0.483 / 0.493 | 0.483 / 0.389 |
| multi_file | 6 | 0.444 / 0.490 | 0.292 / 0.295 | 0.486 / 0.379 |

Dense and fused arms help where the query has no lexical overlap (paraphrased, symptom without identifiers) and hurt exact-identifier ranking (MRR 0.746 to 0.583 even after fusion) and indirect dependency. Per cause class on dev (G / RET-LE / RET-LGE, packed coverage): configuration 0.906 / 0.812 / 0.812; application_code 0.933 / 0.867 / 0.800. Source localisation (file@1) is not improved by embeddings on dev (G 0.226; best 0.258 with RET-LE jina, n = 31).

### "Just more context" null (4500 tokens)

| Slice | G cov | L cov | RET-LGE jina k=60 cov |
|---|---|---|---|
| 45 queries | 0.706 | 0.706 | 0.780 |
| dev | 0.952 | 0.968 | 1.000 |

Raising the budget by 50% lifts every arm; G and L at 4500 tokens reach 0.952 / 0.968 on dev, i.e. context size alone moves coverage by more than the embeddings do at 3000. The fused arm is ahead at 4500 but the margin was not tested for significance.

## 6. Cost

| Item | minilm | jina | nomic |
|---|---|---|---|
| Vector storage, lab (280 chunks, 276 unique) | 0.43 MB live matrix; 0.64 MB namespace | 0.86 MB; 1.06 MB | 0.86 MB; 1.06 MB |
| requests (765 chunks) | 1.2 MB; 1.8 MB | 2.4 MB; 2.9 MB | 2.4 MB; 2.9 MB |
| dev namespace after 31 trees | 4.3 MB (manifests dominate: about 120 KB per tree) | 4.8 MB | 4.8 MB |
| Dev incremental embedding | 329 texts embedded for 31 trees (276 cold + 53 changed); 8347 of 8680 vectors reused | same | same |
| Cold embed time as run via `localhost` (includes about 2 s per batch of delay) | lab 21.5 s, requests 59 s | lab 33 s, requests 114 s | lab 34 s, requests 120 s |
| Cold embed per 100 chunks at idle (`127.0.0.1`) | 1.2 s | 5.7 s | 5.8 s |
| Warm resync | 0.03 s (lab), embeds nothing; asserted in code for every sync | same | same |
| Query-time embed | 15 ms | 25 ms | 25 ms |
| Process peak working set of the run | 210 MB | 242 MB | 211 MB (P5-S06 baseline run: 163 MB) |
| Ollama resident memory (GPU) | 27 MB | 336 MB | 335 MB |
| Model download | 45 MB | 322 MB | 274 MB |

Whole-run runtimes: jina 3074 s, minilm 2743 s, nomic 2907 s, null 555 s (dominated by the 2 s call delay and the bootstrap of 21 pairs). Maintainability: embeddings add a second server dependency (Ollama), per-model namespaces, a per-commit manifest and model-digest bookkeeping; the P5-S07 index (incremental, content-addressed) keeps the re-embedding cost low (changed chunks only). The `verify` tool was not run on the final namespaces.

## 7. All models (fused minus G, dev; full table in `analysis.md`)

| Model | arm | config coverage | app_code coverage | dev packed precision |
|---|---|---|---|---|
| jina | RET-LGE k=60 | -0.094 [-0.188, +0.000] | -0.133 [-0.333, +0.000] | -0.003 [-0.009, +0.002] |
| minilm | RET-LGE k=60 | -0.156 [-0.281, -0.062] | +0.000 [+0.000, +0.000] | +0.001 [-0.005, +0.006] |
| nomic | RET-LGE k=60 | -0.125 [-0.250, -0.031] | -0.133 [-0.333, +0.000] | +0.001 [-0.006, +0.007] |

minilm is the least harmful on application_code (coverage equal to G) and has the best Recall@10 on dev among the fused arms (0.726 vs G 0.839), so the code-trained model was not better here than the 22M general one.

## 8. Limitations

- Small n: 31 dev cases (16 configuration, 15 application_code, all from one lab with one service) and 45 benchmark queries (6 to 10 per type). Cases within a family are mutations of the same code, so they are not independent samples; intervals are wide and descriptive.
- Benchmark labels were written by Claude on Ruhan's behalf, without independent second-person verification (see the P5-S06 doc); query wording may favour lexical overlap in the exact-identifier type.
- RRF is untuned by design (k in {30, 60}, equal weights, top 50 from each list); weighted or learned fusion, other chunk text formats (summaries, docstring-only) and larger models were not tried. Results cannot say that no embedding setup would help.
- Dev only. Frozen test split, `results/final` and RC1 are untouched (code fingerprint `ee3d8d87...` verified equal in all four run summaries). Nothing here concerns repair, diagnosis accuracy or the frozen experiment; retrieval metrics are proxies for what the model sees.
- The harness has no dedup switch, so "with / without dedup" was not run. Budget-matched baselines are only the 4500 null (the packer fills any budget, so tokens are already equal at 3000).
- Harness latency for dense arms is inflated by a 2 s `localhost` resolution delay (section 2); real figures come from the microbenchmark and are single-machine, GPU-backed, one session of other GPU load.
- jina is a community Ollama build (F16 GGUF), loaded by Ollama with a 4096 context; chunks are truncated to 6000 characters by the index text builder, nomic at 2048 and minilm at 256 tokens may truncate long chunks silently (Ollama default). The primary model was fixed before the run; a different choice (e.g. CodeRankEmbed) may behave differently.
- One transient `HTTP 400` crash in the first nomic attempt (section 2); the repeat was unchanged.

## 9. Recommendation (not a decision)

Criteria: recall/precision, MRR/nDCG, source localisation, evidence relevance, token overhead, latency, indexing cost, memory, reliability and maintainability.

- **Keep BM25 + graph (G) as the retrieval configuration; do not adopt embeddings or hybrid fusion** (option A). Evidence: on the real input (dev, anchors and symptom present) G is ahead on packed coverage, Recall@10, nDCG@10 and MRR against every embedding arm and model; H1 and H2 fail by clear margins at both k; embeddings alone win nothing and lose exact-identifier queries; token overhead is zero change (equal budget) while latency, memory, storage and an extra server dependency are added. File-level source localisation is not improved on dev.
- Do not select on one metric: the only places where embeddings look better (Recall@10 and packed coverage on the 45 free-text queries, `paraphrased_bug` and `symptom_no_identifier`) are not statistically distinguishable from zero on the pooled set and do not carry over to the pipeline's anchored inputs.
- If the owner wants to keep the option open at low cost: the P5-S07 index code stays available; a possible narrow follow-up is a dense fallback only when the query has no identifiers and BM25 returns weak candidates, tested on a larger label set made by someone other than Claude. That is a new hypothesis, not supported yet.
- **If a hybrid had improved retrieval**, adoption would still require (not run): a fresh fingerprinted release candidate (the frozen files are not edited here), downstream diagnosis and repair on a harder case set than the near-saturated RC1 benchmark, with preregistered conditions, replicates and owner-approved spend (P5-S11), a check that no hidden test or gold file enters the index, and fixing `OllamaEmbedder` to use `127.0.0.1`. None of this is proposed now.

## 10. Reproducibility

| Item | Value |
|---|---|
| Commit | runs recorded `9f2eb794db0e8a14845a8e26815e4a88c38150e2` in their provenance (working tree with uncommitted paths at that time); HEAD when the doc was finished: `dd3fae26ed84ffa454f6744c056c61d7e07c2931` |
| Code | `backend/traceforge/retrieval_next/` (`dense.py`, `hybrid.py`, `bench_plugin.py`, `analyze.py`), tests `backend/tests/retrieval_next/` (10 tests) |
| Commands | `cd backend && .venv/Scripts/python.exe -m traceforge.retrieval_bench --plugin traceforge.retrieval_next.bench_plugin --suite both --run-id p5s08-jina --methods RET-L RET-G RET-E@jina RET-LE@jina:k30 RET-LE@jina:k60 RET-LGE@jina:k30 RET-LGE@jina:k60` (same with `minilm`, `nomic`; null: `--budget 4500 --run-id p5s08-null4500 --methods RET-L RET-G RET-LGE@jina:k60`); analysis: `python -m traceforge.retrieval_next.analyze --runs minilm=... jina=... nomic=... --null4500 ... --index-root runs/bench_repos/embed_index --out results/retrieval/p5s08-analysis`; evidence bundles: `python -m traceforge.agent.lab_collect --manifest datasets/manifests/dev.json --case <id>` |
| Models | section 2: ids, digests (`1b226e2802db`, `9fe680d4d58b`, `0a109f422b47`), dims, contexts; index preprocessing `p1` (minilm, jina) and `p1+pfx` (nomic prefixes), batch size 32, float32, cosine |
| Versions | Python 3.12.15, numpy 2.5.5, networkx 3.7, rank-bm25 0.2.2, pydantic 2.14.4, Ollama 0.40.17 |
| Hardware | Windows 11 (10.0.26200), AMD Ryzen 5 2600 (12 threads), 16 GB RAM, NVIDIA GTX 1660 SUPER 6 GiB; embeddings ran on the GPU via Ollama |
| Seeds | bootstrap seed 20261125 (10,000 resamples, percentile 95%); no other randomness (embeddings deterministic, determinism of 3 repeats enforced by the harness, ties deterministic) |
| Datasets | `repos.json` and query files hashed in each `summary.json`; dev manifest `c939167dad58782c47a1300dccdfa46f101e04c034b5a0ae430541a48c98d68f`; 31 of 33 scored |
| Runtime | 3074 s, 2743 s, 2907 s, 555 s (see section 6) |
| RC1 fingerprint | `ee3d8d873a6e939451650d031a919799138e621859f79bdd91994af3f6456b51` before and after (all four run summaries) |
| Index | `runs/bench_repos/embed_index/` (git-ignored, 26 MB, regenerable); `build_log.jsonl` copied to `results/retrieval/p5s08-analysis/` |

## Note on reported latencies (added after the run)
The runs above reached Ollama through `localhost`, which on this Windows machine adds about 2 s per call (idle `127.0.0.1` calls: 15/25/25 ms per query embedding for minilm/jina/nomic). Dense-arm latency and indexing times in the tables are therefore inflated; the rankings and quality metrics are unaffected. `OllamaEmbedder` now defaults to `http://127.0.0.1:11434`. The runs were not repeated.
