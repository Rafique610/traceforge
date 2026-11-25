# Retrieval benchmark and baselines: RET-L and RET-G (P5-S06)

Status: results of an engineering validation of the harness. Labels were written by Claude on behalf of Ruhan and have not had an independent second-person check. No superiority claim is made. Run id `p5s06-baseline-run1`; `run2` is an identical re-run (rankings byte-identical, `cmp` verified).

**Reproduced by Rafique, 25 Nov 2026** (runs `review-both-1` and `review-both-2`, his laptop): the three repo suites give exactly the numbers below; all 33 dev bundles were collected (`lab_collect --jobs 3`, 33 contract-valid, 0 secret leaks), so the dev split now scores **31 cases** instead of 12. Sections 3.1 (dev rows), 3.3, 3.4 (dev rows) and 3.5 (dev rows) show the 31-case run; Ruhan's 12-case dev numbers are kept in section 3.6 for the record. Rankings byte-identical across the two runs; `code_fingerprint()` unchanged.

## 1. What was built (facts)

| Item | Where |
|---|---|
| Harness package | `backend/traceforge/retrieval_bench/` (registry, repo context, shared packer, metrics, seeded paired bootstrap and sign test, repo and dev loaders, report writer, CLI) |
| Benchmark data | `benchmarks/retrieval/` (`repos.json` pins, `queries/*.json` labels, `second_review.csv`, README with the labelling protocol) |
| Tests | `backend/tests/retrieval_bench/` (25 tests: hand-computed metrics, bootstrap seeding, equal-budget packing, gold never reaches retrievers, determinism, label validity) |
| Run output | `results/retrieval/p5s06-baseline-run1/` and `run2/` (`per_query.csv`, `summary.csv`, `comparisons.csv`, `builds.csv`, `rankings.json`, `summary.json`, `report.md`) |
| Command | `cd backend && .venv/Scripts/python.exe -m traceforge.retrieval_bench --suite both --methods RET-L RET-G` |

The harness reuses `traceforge.retrieval` (corpus, lexical index, anchors, `rank`, `context_budget.pack`) and `traceforge.codeintel` as read-only libraries. No file of the 28 RC1-fingerprinted set, `results/final` or `datasets/` was edited; the run records `code_fingerprint()` = `ee3d8d873a6e939451650d031a919799138e621859f79bdd91994af3f6456b51` (equal to the RC1 value `ee3d8d87...`). No model, provider or network call is made by the harness (`llm_or_provider_calls: 0`).

### Arms

- **RET-L**: BM25 (`rank_bm25.BM25Okapi`, identifier-aware tokenizer, top 50 candidates) plus the L-arm anchors (innermost 2 trace frames forced, config keys literally named in the evidence forced), score 0.30 lex + 0.25 anchor. Library call: `retrieval.retrieve.rank(..., "L")`.
- **RET-G**: RET-L plus graph features (2-hop proximity and expansion, config binding, test link, uncertainty penalty; symptom anchors from failing visible tests and routes). Library call: `rank(..., "G")`, default `GraphFeatures`, weights untouched.
- Both rank the same candidate pool; the harness truncates the ranked list at K = 50 and returns `Chunk.hit_id`s (bare `cfg:KEY` for config keys).

### Query input

- **Repos (free-text suites):** the query is a plain string. To drive the L/G anchors it is wrapped in a synthetic one-item `EvidenceBundle` (kind `issue`; plus a `log` item when the text contains a traceback). The queries here contain no tracebacks and no failing tests, so the anchors are empty for them, apart from config keys that are literally named; in effect RET-L is plain BM25 and RET-G adds only graph proximity to those few anchors. This is why RET-G equals RET-L on the repos.
- **Dev split:** v5 evidence = saved bundle + visible-test symptom + deterministic findings, rebuilt by running only the visible reproducer and visible suite on the faulty base commit in the local Docker sandbox (approach of `scripts/analysis_symptom_evidence.py`; no hidden suite, no gold, no model). Gold comes from the dev manifest and goes only to the scorer. The frozen test split is refused by the loader.

### Equal-budget packing and metrics

Every method's ranked list goes through the same `context_budget.pack` at 3000 tokens (80% usable = 2400, chars/4, at most 80 lines per excerpt, already-shown lines skipped) with neutral reasons, so no method pays a different header cost. The packed context therefore differs slightly from the production `retrieve()` bundle (which carries per-hit reasons).

- Recall@K, Precision@K (divided by K), MRR (full ranking), nDCG@10 (binary gain), file_hit@K (any of the top K ids is in a gold file; source localisation), symbol_hit@1.
- Packed context: gold coverage (share of gold ids kept inside the budget), packed precision, packed MRR, tokens used.
- Cost: latency per query (median of 3 repeats, build excluded), index/base build time, peak Python heap (`tracemalloc`, cold rebuild), whole-process peak working set, persisted storage.
- Differences: paired bootstrap (10,000 resamples, seed 20261125 combined with suite, type, arms and metric, percentile 95% CI), exact two-sided sign test.

## 2. Repositories and labels

| Tier | Repo | Pin | License | Size | Queries | Chunks |
|---|---|---|---|---|---|---|
| small | pallets/itsdangerous 2.2.0 | `096c8d42545d3b68ea21a4f890fb2b2d8979c0bd` | BSD-3-Clause | 139 KB | 15 | 144 |
| medium | psf/requests v2.32.3 | `0e322af87745eff34caffe4df68456ebc20d9068` | Apache-2.0 | 5.2 MB | 15 | 765 |
| complex | this repo's `lab/` (shop_api, worker, compose, env example, settings, tests) | `9f2eb794db0e8a14845a8e26815e4a88c38150e2`, lab tree `3b9ea611...` | project-internal | 63 KB | 15 | 280 |

Total clone size under 10 MB. 45 queries, 98 gold units (`second_review.csv` has one row per unit), six query types per repo (exact identifier or error message, paraphrased bug, symptom without identifiers, indirect dependency, configuration, multi-file). Gold = source units (file + qualified symbol, or `cfg:KEY`) with a one-line justification each, verified by reading the code at the pinned commit; never derived from any retrieval output.

## 3. Results (saved run, K = 50, budget 3000 tokens)

Means over queries. File-level and packed metrics as defined above.

### 3.1 Per repository

| suite | method | n | R@1 | R@5 | R@10 | P@5 | MRR | nDCG@10 | file@1 | packed gold cov. | tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| complex_lab | RET-G | 15 | 0.089 | 0.367 | 0.578 | 0.173 | 0.409 | 0.393 | 0.533 | 0.744 | 2390 |
| complex_lab | RET-L | 15 | 0.089 | 0.367 | 0.578 | 0.173 | 0.409 | 0.393 | 0.533 | 0.744 | 2390 |
| dev | RET-G | 31 | 0.097 | 0.565 | 0.839 | 0.181 | 0.390 | 0.479 | 0.226 | 0.919 | 2393 |
| dev | RET-L | 31 | 0.097 | 0.290 | 0.790 | 0.110 | 0.306 | 0.411 | 0.226 | 0.919 | 2392 |
| medium_requests | RET-G | 15 | 0.167 | 0.444 | 0.511 | 0.147 | 0.396 | 0.387 | 0.400 | 0.511 | 2393 |
| medium_requests | RET-L | 15 | 0.167 | 0.444 | 0.511 | 0.147 | 0.385 | 0.381 | 0.400 | 0.511 | 2393 |
| small_itsdangerous | RET-G | 15 | 0.233 | 0.411 | 0.578 | 0.120 | 0.386 | 0.420 | 0.533 | 0.611 | 2391 |
| small_itsdangerous | RET-L | 15 | 0.233 | 0.411 | 0.578 | 0.120 | 0.386 | 0.420 | 0.533 | 0.611 | 2391 |

### 3.2 Pooled over the three repos (45 queries), per query type

| qtype | method | n | R@1 | R@5 | R@10 | P@5 | MRR | nDCG@10 | file@1 | packed gold cov. | tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | RET-G | 45 | 0.163 | 0.407 | 0.556 | 0.147 | 0.397 | 0.400 | 0.489 | 0.622 | 2392 |
| ALL | RET-L | 45 | 0.163 | 0.407 | 0.556 | 0.147 | 0.393 | 0.398 | 0.489 | 0.622 | 2392 |
| configuration | RET-G | 10 | 0.083 | 0.400 | 0.567 | 0.180 | 0.383 | 0.397 | 0.500 | 0.650 | 2392 |
| configuration | RET-L | 10 | 0.083 | 0.400 | 0.567 | 0.180 | 0.366 | 0.389 | 0.500 | 0.650 | 2392 |
| exact_identifier | RET-G | 10 | 0.550 | 0.900 | 1.000 | 0.220 | 0.746 | 0.814 | 0.700 | 1.000 | 2386 |
| exact_identifier | RET-L | 10 | 0.550 | 0.900 | 1.000 | 0.220 | 0.746 | 0.814 | 0.700 | 1.000 | 2386 |
| indirect_dependency | RET-G | 7 | 0.000 | 0.286 | 0.548 | 0.114 | 0.212 | 0.282 | 0.571 | 0.643 | 2393 |
| indirect_dependency | RET-L | 7 | 0.000 | 0.286 | 0.548 | 0.114 | 0.212 | 0.282 | 0.571 | 0.643 | 2393 |
| multi_file | RET-G | 6 | 0.083 | 0.306 | 0.444 | 0.200 | 0.490 | 0.359 | 0.500 | 0.611 | 2395 |
| multi_file | RET-L | 6 | 0.083 | 0.306 | 0.444 | 0.200 | 0.490 | 0.359 | 0.500 | 0.611 | 2395 |
| paraphrased_bug | RET-G | 6 | 0.083 | 0.250 | 0.417 | 0.100 | 0.312 | 0.269 | 0.333 | 0.417 | 2392 |
| paraphrased_bug | RET-L | 6 | 0.083 | 0.250 | 0.417 | 0.100 | 0.312 | 0.269 | 0.333 | 0.417 | 2392 |
| symptom_no_identifier | RET-G | 6 | 0.000 | 0.000 | 0.056 | 0.000 | 0.048 | 0.024 | 0.167 | 0.139 | 2395 |
| symptom_no_identifier | RET-L | 6 | 0.000 | 0.000 | 0.056 | 0.000 | 0.048 | 0.024 | 0.167 | 0.139 | 2395 |

### 3.3 Dev split (v5 evidence; 31 cases scored, 8 variant groups)

| qtype | method | n | R@1 | R@5 | R@10 | P@5 | MRR | nDCG@10 | file@1 | packed gold cov. | tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | RET-G | 31 | 0.097 | 0.565 | 0.839 | 0.181 | 0.390 | 0.479 | 0.226 | 0.919 | 2393 |
| ALL | RET-L | 31 | 0.097 | 0.290 | 0.790 | 0.110 | 0.306 | 0.411 | 0.226 | 0.919 | 2392 |
| application_code | RET-G | 15 | 0.000 | 0.467 | 0.867 | 0.093 | 0.179 | 0.333 | 0.000 | 0.933 | 2392 |
| application_code | RET-L | 15 | 0.000 | 0.067 | 0.867 | 0.013 | 0.120 | 0.278 | 0.000 | 0.933 | 2390 |
| configuration | RET-G | 16 | 0.188 | 0.656 | 0.812 | 0.263 | 0.589 | 0.617 | 0.438 | 0.906 | 2394 |
| configuration | RET-L | 16 | 0.188 | 0.500 | 0.719 | 0.200 | 0.480 | 0.535 | 0.438 | 0.906 | 2393 |

Scored: 31 of 33 dev cases. Skipped (no retrieval target): shop_api-003 (runtime_dependency), shop_api-004 (insufficient_evidence). The 31 cases come from 8 variant groups, so they are not 31 independent samples.

### 3.4 RET-G minus RET-L (paired; positive = G higher)

| suite | metric | G - L | 95% CI (paired bootstrap) | G better / L better / tie | sign p |
|---|---|---|---|---|---|
| ALL (n=45) | recall@5 | +0.000 | [+0.000, +0.000] | 0 / 0 / 45 | 1.000 |
| ALL (n=45) | recall@10 | +0.000 | [+0.000, +0.000] | 0 / 0 / 45 | 1.000 |
| ALL (n=45) | mrr | +0.004 | [+0.000, +0.011] | 1 / 0 / 44 | 1.000 |
| ALL (n=45) | ndcg@10 | +0.002 | [+0.000, +0.005] | 1 / 0 / 44 | 1.000 |
| ALL (n=45) | gold_coverage_packed | +0.000 | [+0.000, +0.000] | 0 / 0 / 45 | 1.000 |
| complex_lab (n=15) | recall@5 | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| complex_lab (n=15) | recall@10 | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| complex_lab (n=15) | mrr | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| complex_lab (n=15) | ndcg@10 | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| complex_lab (n=15) | gold_coverage_packed | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| dev (n=31) | recall@5 | +0.274 | [+0.145, +0.419] | 11 / 0 / 20 | 0.001 |
| dev (n=31) | recall@10 | +0.048 | [+0.000, +0.097] | 3 / 0 / 28 | 0.250 |
| dev (n=31) | mrr | +0.084 | [+0.045, +0.129] | 20 / 3 / 8 | <0.001 |
| dev (n=31) | ndcg@10 | +0.069 | [+0.030, +0.112] | 17 / 4 / 10 | 0.007 |
| dev (n=31) | gold_coverage_packed | +0.000 | [-0.097, +0.097] | 1 / 1 / 29 | 1.000 |
| medium_requests (n=15) | recall@5 | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| medium_requests (n=15) | recall@10 | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| medium_requests (n=15) | mrr | +0.011 | [+0.000, +0.033] | 1 / 0 / 14 | 1.000 |
| medium_requests (n=15) | ndcg@10 | +0.005 | [+0.000, +0.016] | 1 / 0 / 14 | 1.000 |
| medium_requests (n=15) | gold_coverage_packed | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| small_itsdangerous (n=15) | recall@5 | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| small_itsdangerous (n=15) | recall@10 | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| small_itsdangerous (n=15) | mrr | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| small_itsdangerous (n=15) | ndcg@10 | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |
| small_itsdangerous (n=15) | gold_coverage_packed | +0.000 | [+0.000, +0.000] | 0 / 0 / 15 | 1.000 |

On the three repos the two arms are identical on every recall metric and differ only in MRR on one query (medium_requests). On dev (31 cases, 8 variant groups), G is higher on Recall@5, MRR and nDCG@10 with intervals that exclude zero (application_code Recall@5 +0.400, p = 0.031; configuration MRR +0.109, p = 0.008). Packed gold coverage is equal (0.919 both; G better on one case, L on another): G moves gold higher in the ranking, but within the 2400 usable tokens both arms end up holding the same gold. Cases inside a variant group are not independent, so read this as strong descriptive evidence on dev, not as a test-split result.

### 3.5 Cost

| repo | chunks | graph s | corpus s | BM25 s | base build s | peak Python heap MB | corpus text KB | persisted storage |
|---|---|---|---|---|---|---|---|---|
| small_itsdangerous | 144 | 0.128 | 0.015 | 0.010 | 0.152 | 2.06 | 50 | 0 B |
| medium_requests | 765 | 0.553 | 0.063 | 0.077 | 0.693 | 16.34 | 393 | 0 B |
| complex_lab | 280 | 0.156 | 0.013 | 0.014 | 0.183 | 2.34 | 62 | 0 B |
| dev (mean of 31 case trees) | 280 | 0.244 | 0.013 | 0.012 | 0.270 | 2.38 (max) | 62 | 0 B |

Index build for RET-L/RET-G is the base build above (graph, corpus, BM25; there is no separate per-method index), nothing is persisted. Whole-process peak working set of the run: 162.7 MB (includes Python and libraries). Query latency (graph and index prebuilt):

| suite | method | median-of-3 query latency, mean over queries (ms) |
|---|---|---|
| ALL | RET-G | 3.6 |
| ALL | RET-L | 3.7 |
| complex_lab | RET-G | 2.4 |
| complex_lab | RET-L | 2.6 |
| dev | RET-G | 15.0 |
| dev | RET-L | 10.9 |
| medium_requests | RET-G | 6.6 |
| medium_requests | RET-L | 6.8 |
| small_itsdangerous | RET-G | 1.8 |
| small_itsdangerous | RET-L | 1.7 |

Hardware: Windows-11-10.0.26200-SP0, AMD64 Family 23 Model 8 Stepping 2, AuthenticAMD, 12 logical CPUs, Python 3.12.15; packages {'rank-bm25': '0.2.2', 'networkx': '3.7', 'numpy': '2.5.5', 'pydantic': '2.14.4'}. Run time 26.7 s (v5 dev bundles were rebuilt once earlier in the sandbox and cached under runs/bench_repos/dev_evidence_v5; this run reused them).

### 3.6 Earlier 12-case dev run (Ruhan, `p5s06-baseline-run1`), kept for the record

| qtype | method | n | R@1 | R@5 | R@10 | P@5 | MRR | nDCG@10 | file@1 | packed gold cov. | tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | RET-G | 12 | 0.125 | 0.792 | 0.917 | 0.233 | 0.436 | 0.542 | 0.250 | 0.917 | 2393 |
| ALL | RET-L | 12 | 0.125 | 0.375 | 0.875 | 0.133 | 0.369 | 0.474 | 0.250 | 1.000 | 2391 |
| application_code | RET-G | 7 | 0.000 | 0.714 | 0.857 | 0.143 | 0.200 | 0.352 | 0.000 | 0.857 | 2393 |
| application_code | RET-L | 7 | 0.000 | 0.143 | 0.857 | 0.029 | 0.136 | 0.285 | 0.000 | 1.000 | 2390 |
| configuration | RET-G | 5 | 0.300 | 0.900 | 1.000 | 0.360 | 0.767 | 0.808 | 0.600 | 1.000 | 2393 |
| configuration | RET-L | 5 | 0.300 | 0.700 | 0.900 | 0.280 | 0.695 | 0.739 | 0.600 | 1.000 | 2393 |

Scored: 12 of 33 dev cases. Skipped: 19 cases without a saved EvidenceBundle (collecting these needs the live faulty lab; not done here, never invented) and:

- shop_api-003: no retrieval target (runtime_dependency)
- shop_api-004: no retrieval target (insufficient_evidence)

G minus L on those 12: recall@5 +0.417 [+0.167, +0.667] p = 0.031; MRR +0.067 [+0.017, +0.132]; nDCG@10 +0.068 [+0.014, +0.123]; packed coverage -0.083 [-0.250, +0.000].

## 4. Observations (descriptive only)

- Exact identifier and error-message queries are the strong case for BM25: pooled Recall@5 0.90 and Recall@10 1.00 on 10 queries.
- Symptom queries without source identifiers are the weak case for both arms (pooled Recall@10 0.056 on 6 queries): lexical overlap is the only signal and there is no anchor. This is the gap a dense or hybrid arm (RET-E, RET-LE, RET-LGE) is meant to test.
- Gold coverage inside the packed 2400-token context is slightly higher than Recall@10 on the repos (0.62 vs 0.56 pooled), because the packer takes more than ten hits when they are short; packed precision is low (about 8%) because the packer fills the budget, as noted in the architecture review.
- Dev evidence includes failing-test symptoms and trace anchors, which is why dev numbers are much higher than the free-text repo numbers; they are not comparable across suites.

## 5. Limitations

- Small n: 15 queries per repo, 45 pooled, 31 dev cases from 8 variant groups; intervals are wide and most per-type cells have 6 to 10 queries. Queries within a repo are not independent samples of a population.
- Labels were authored by Claude (the same model family that helps build this system) on Ruhan's behalf, from the code at the pinned commit. They need an independent second-person spot check (`benchmarks/retrieval/second_review.csv`). Query wording can favour lexical overlap with the code in the exact-identifier type by construction.
- The repo suites feed free text, so the trace-frame and symptom anchors that define L and G in the real pipeline are mostly absent; they exercise the lexical part. The dev loader is the only place where the anchors and graph features are active.
- Dev: 31 of 33 cases (2 non-repairable), from 8 variant groups only. The dev lab is the same code as benchmark tier (c) but queries and labels are separate.
- Corpus limits shared by all methods: overloaded methods are indexed by their first stub only; inheritance edges do not exist; class headers are capped at 12 lines.
- Packing uses neutral reasons, so packed tokens are not byte-identical to production bundles; chars/4 is an estimate.
- This is engineering validation of the harness and baselines. No arm is claimed better than another; no hypothesis from the review (H1 to H4) is tested here.

## 6. Adding methods (RET-E, RET-LE, RET-LG, RET-LGE)

Registration API (`backend/traceforge/retrieval_bench/registry.py`): a retriever is `(ctx: RepoContext, query_text: QueryText, k: int) -> list[str]` returning the top-k `Chunk.hit_id`s, best first, no duplicates. `query_text` is a `str`; `.evidence` and `.service` are optional extras. The harness handles packing, scoring, latency, build timing, determinism check (3 repeats must agree) and the gold-leak check.

```python
from traceforge.retrieval_bench.registry import register, get

@register("RET-E", model_id="<model id@revision>", settings={"dims": 768})
class DenseRetriever:
    def prepare(self, ctx):                       # optional; timed as index_build_s, once per repo
        ctx.state["RET-E"] = embed(ctx.corpus.chunks)   # ctx.corpus.chunks: id, path, text, lines
    def __call__(self, ctx, query_text, k):
        return top_k_ids(ctx.state["RET-E"], str(query_text), k)
    def storage_bytes(self, ctx):                 # optional; default 0
        return ctx.state["RET-E"].nbytes

@register("RET-LE")                                # fusion reuses the baselines
def ret_le(ctx, q, k):
    return rrf([get("RET-L")(ctx, q, 50), get("RET-E")(ctx, q, 50)], k=60)[:k]
```

Run: `python -m traceforge.retrieval_bench --plugin <module that registers> --methods RET-L RET-G RET-E RET-LE`. Provenance records each method's `model_id` and `settings`. Pairwise comparisons are produced for every method pair.

## 7. Reproduction and checks

- Clone commands and pins: `benchmarks/retrieval/README.md`. The harness verifies HEAD (or tree hash) against `repos.json`.
- Dataset hashes recorded in `summary.json`: `repos.json`, each query file, `datasets/manifests/dev.json` (`c939167dad58782c47a1300dccdfa46f101e04c034b5a0ae430541a48c98d68f`).
- Determinism: `cmp results/retrieval/p5s06-baseline-run1/rankings.json .../run2/rankings.json` identical.
- Tests: `cd backend && .venv/Scripts/python.exe -m pytest tests/retrieval_bench -q -p no:cacheprovider` (25 passed).
- Provenance block (git SHA `9f2eb794db0e8a14845a8e26815e4a88c38150e2`, working tree had 9 uncommitted paths at run time from other work) is in `summary.json` and `report.md`.
