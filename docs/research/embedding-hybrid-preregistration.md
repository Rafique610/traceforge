# Preregistration: embedding retrieval and hybrid fusion (P5-S08)

Written 2026-11-25 BEFORE any embedding-arm retrieval run (no `RET-E`, `RET-LE`, `RET-LGE` number existed when this was written). Author: Ruhan's session at the owner's direction (task owner Rafique, reviewer Rafique). Status of ADR 0003 stays PROPOSED. Repository HEAD `9f2eb794db0e8a14845a8e26815e4a88c38150e2` with uncommitted work (nothing may be committed by this session, so the file's SHA-256 is recorded in the evaluation doc instead of a commit). Design basis: `retrieval-architecture-review.md` sections 2.2, 2.5, 5.

## 1. Scope and rules

- Retrieval-level evidence only. Nothing here says anything about diagnosis, repair or G1 superiority.
- Zero LLM or provider calls; zero AxForge / BeatAPI. Embeddings come from the local Ollama server only.
- Gold labels are read only by the scorer. The benchmark repos (45 queries, Claude-authored labels) and the TraceForge DEV split are used; the test split and `results/final` are never touched. RC1 code fingerprint must equal `ee3d8d873a6e939451650d031a919799138e621859f79bdd91994af3f6456b51` before and after.
- Harness: `traceforge.retrieval_bench` (K = 50, packed budget 3000 tokens = 2400 usable, identical `pack()` for all arms, determinism check of 3 repeats, 10,000-resample seeded paired bootstrap).
- One run per (model, arm, k). No tuning loops, no weight search, no query rewriting, no re-runs after seeing results (a re-run is allowed only to repair a crash and must be reported).

## 2. Arms

| Name | Definition |
|---|---|
| RET-L, RET-G | existing baselines (P5-S06), unchanged |
| RET-LG | alias of RET-G (identical ranking, checked by a test) |
| RET-E | dense top-50 by cosine over the same chunks, query = the exact string BM25 receives, no rewrite, no anchors, no graph |
| RET-LE (= ablation "L+E") | forced anchors first (as in L), then RRF(k) of the L ranking (top 50) and the dense top 50 |
| RET-LGE (= ablation "G+E") | forced anchors first (as in G), then RRF(k) of the G ranking (top 50) and the dense top 50 |

RRF score = sum over lists of 1/(k + rank), rank starting at 1; ties broken by best rank in the base (L or G) list, then by chunk id. k in {30, 60}. Dense uses the incremental index of P5-S07 (`traceforge.index`), cosine, flat numpy. Embedding text per chunk is the P5-S07 text (kind, name, source lines, at most 6000 chars). Model-specific query/document prefixes are part of the model preprocessing (version tag recorded), not a query rewrite.

## 3. Models (fixed before the run)

Compatibility is checked and recorded before any retrieval run (size, dims, context, time per 100 chunks). Selected:

| Tag | Role | Model |
|---|---|---|
| minilm | general baseline (always evaluated) | `all-minilm:22m`, 384-d |
| jina | **primary model for the go / no-go verdict** (the one small code-trained model of the plan) | `unclemusclez/jina-embeddings-v2-base-code`, 768-d |
| nomic | exploratory, reported but NOT eligible for the verdict | `nomic-embed-text`, 768-d |

The verdict uses the primary model only, to avoid choosing the best of several models after the fact. If the primary model fails to run, the verdict falls back to minilm and the doc says so.

## 4. Hypotheses and thresholds (from review 5.4)

Metric names are the harness columns. "Fused" = RET-LGE (primary model). A hypothesis HOLDS only if the point estimate meets the threshold at BOTH k = 30 and k = 60. The paired-bootstrap 95% CI is reported for every comparison; a point-estimate pass whose CI includes values below the threshold is labelled "not distinguishable from failing".

- **H1.** On dev configuration cases, `gold_coverage_packed` (gold-in-packed-context recall at the 3000 token budget) of the fused arm minus RET-G is >= +0.15 absolute.
- **H2.** On dev application_code cases, `gold_coverage_packed` of the fused arm is not lower than RET-G by more than 0.05 (G minus fused <= 0.05).
- **H3.** Precision at equal tokens: dev (all repairable cases) `precision_packed` of the fused arm >= RET-G (difference >= 0). Reported also on the pooled 45 benchmark queries.
- **H4.** On the identifier-heavy benchmark queries (type `exact_identifier`, 10 queries across the three repos), RET-E (primary model) has lower MRR than RET-L. Secondary: also lower recall@5. Holds if the MRR difference (E minus L) is below 0.

Decision rule (ADR 0003): **go** only if H1 and H2 hold on dev; otherwise no-go and option A (keep L / G) is recorded. H3 and H4 are reported, they do not change the rule.

### Known risk written down in advance
The earlier harness run (12 of 33 dev cases) already showed RET-G with `gold_coverage_packed` = 1.000 on dev configuration cases, so a +0.15 gain may be impossible by ceiling. If so H1 is reported as FAIL (ceiling), not redefined.

## 5. Secondary, descriptive (no thresholds)

Recall@1/5/10, Precision@1/5/10, MRR, nDCG@10, file_hit@1 (source localisation), gold coverage in the packed context (evidence coverage; for config cases this is the gold config key), tokens used, query latency, index build time, memory, storage; per query type (repos) and per cause class (dev); the direct comparisons G vs RET-LGE vs RET-E vs the best hybrid (selected by the rule below); RET-L / RET-G at a 1.5x budget (4500) as the "just more context" null; every model. The best hybrid is the fused arm with the highest mean rank over {recall@10, mrr, ndcg@10, gold_coverage_packed} pooled over dev and the 45 queries, primary model first, ties to the lower token count; this is descriptive and is not the verdict arm. No other multiplicity correction is applied: n is small, intervals are descriptive.

## 6. Data

- Benchmark: three pinned repos, 45 queries (`benchmarks/retrieval/`), unchanged.
- Dev: `datasets/manifests/dev.json` (33 cases, repairable ones scored). Missing saved evidence bundles are collected locally with `python -m traceforge.agent.lab_collect` (no tokens); symptom evidence is rebuilt exactly as in P5-S06. Any case that cannot be collected is listed as skipped.
- Dedup: the shared packer's line-overlap skipping is always on (the harness has no switch); a "without dedup" variant is not run (stated as a limitation).

## 7. Reproducibility record (filled in the evaluation doc)

Commit SHA, model id / digest / dims / context, preprocessing version, batch size 32, package versions, hardware, seeds (bootstrap seed 20261125), runtime, determinism check, fingerprint before and after.
