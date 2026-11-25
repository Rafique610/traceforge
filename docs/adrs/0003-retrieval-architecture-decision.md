# ADR 0003: Retrieval architecture decision

Status: PROPOSED (not accepted; needs project-owner approval)
Steps: P5-S06, P5-S07, P5-S08 (deliverable). Proposed to satisfy the "graph decision ADR" prerequisite of P5-S01 and P5-S03.
Design: [retrieval-architecture-review.md](../research/retrieval-architecture-review.md). Decision D36, assumption AS11, question Q16.

## Context
Retrieval is BM25 over graph-derived chunks (L) plus a 2-hop graph walk (G). No embeddings exist (verified 24 Nov 2026). RC1 (fingerprint `ee3d8d87...`) is frozen. Frozen-set offline recall in the sent context is 23/29 (L) and 24/29 (G); exact diagnosis was 28 to 29 of 29, so the benchmark is near saturation. Embedding availability on the machine was unconfirmed at the time of writing (AS11); see the Outcome section below for the models that were run.

## Options
| Option | Summary |
|---|---|
| A. Keep L / G only | No change; embeddings stay "optional" (D18) and are explicitly dropped |
| B. Dense arm RET-E | Local embedding model, numpy flat store |
| C. Hybrid RET-LE / RET-LGE | Reciprocal Rank Fusion (k = 60) of BM25 or G with dense, forced anchors first |
| D. C plus reranking | Cross-encoder on the same top-50 (P5-S09, optional) |
| Rejected up front | pgvector (image change), FAISS, 1.5B to 7B models, hosted embeddings, LLM query rewriting, indexes containing hidden tests or gold |

## Decision criteria (preregistered in P5-S08 before any run)
Dev split only; equal 3000-token budget; paired bootstrap 95% CIs. **Go** only if H1 (fused arm raises gold-in-packed-context recall on dev configuration cases over G by >= 0.15 absolute) and H2 (no application_code loss beyond 0.05) hold; H3 (precision at equal tokens >= G) and H4 (E alone worse than BM25 on identifier-heavy queries) are reported. Otherwise no-go and option A is recorded.

## Decision
**None yet.** To be filled from the P5-S08 results and then approved or rejected by the project owner. Until then RC1 and all frozen artifacts are unchanged, and nothing in the product path imports embedding code.

## Consequences
These describe what would follow from each decision; none has been decided.
- Go: P5-S09 (optional) and P5-S11 (needs owner spend approval) may start; embedding code stays in new modules outside the fingerprint list; any wiring into a frozen condition needs a new fingerprinted release candidate.
- No-go: embeddings are dropped from P2-S03's open checklist item; manifest and cache code from P5-S07 remains available.
- If the owner accepts this ADR, it also satisfies the graph-decision prerequisite of P5-S01 / P5-S03 only to the extent it records whether graph changes enter the main experiment (the A3 graph stays frozen by default).

## PROPOSED addendum (25 Nov 2026): decision gate for traversal and impact capabilities
Design: [root-cause-impact-regression-design.md](../research/root-cause-impact-regression-design.md). Decision D37 (proposed), assumption AS12, questions Q17 and Q18. Tasks P5-S12 to P5-S17 add an overlay with evidence classes, bidirectional traversal and ranking, a change-impact report with visible-test selection, and a conditional regression-aware repair validation (RC2 only). Gate: the capabilities are kept only if the thresholds preregistered in P5-S16 pass on hand-verified fixtures; Tier 2 (P5-S13, P5-S14) and P5-S17 only after the MVP shows a measurable gain and the owner approves. **Decision: none yet** (blank). Nothing here changes RC1.

## Outcome of P5-S08 (25 Nov 2026, evidence for the owner; decision NOT recorded)
Full evidence: [embedding-hybrid-evaluation.md](../research/embedding-hybrid-evaluation.md); preregistration [embedding-hybrid-preregistration.md](../research/embedding-hybrid-preregistration.md); runs `results/retrieval/p5s08-*`. Retrieval-level only (no diagnosis or repair, no G1 claim); 0 LLM/provider calls; RC1 fingerprint unchanged. Models run locally through Ollama: `all-minilm:22m` (384-d), `unclemusclez/jina-embeddings-v2-base-code` (768-d, primary, 322 MB), `nomic-embed-text` (768-d, exploratory, 274 MB). Data: 31 of 33 dev cases (the 19 missing evidence bundles were collected locally) and the 45 benchmark queries; equal 3000-token budget.

| Preregistered test (primary model jina, both RRF k) | Result | Pass |
|---|---|---|
| H1 dev configuration coverage, RET-LGE minus G >= +0.15 | -0.094 [-0.188, +0.000] (G already 0.906) | FAIL |
| H2 dev application_code coverage loss <= 0.05 | loss 0.133 [-0.333, +0.000] | FAIL |
| H3 dev packed precision >= G | -0.004 [-0.010, +0.002] | FAIL (tiny) |
| H4 E alone worse than BM25 on exact_identifier (MRR) | 0.384 vs 0.746, -0.362 [-0.618, -0.120] | PASS |

Decision rule (H1 and H2 on dev): **no-go**. Other models agree in sign (minilm -0.156, nomic -0.125 on configuration coverage, CIs exclude 0). G beats G+E and E alone on dev coverage, Recall@10 and nDCG@10. On the 45 free-text queries fused arms are nominally higher (Recall@10 0.607 vs 0.556) but not distinguishable from zero; the gain is confined to paraphrased and identifier-free queries (n = 6 each) and exact-identifier MRR drops (0.746 to 0.583 after fusion). Cost: equal tokens, 15 to 25 ms per query embed (idle, GPU), 1.2 to 5.8 s per 100 chunks cold, under 1 MB per 280-chunk tree, 27 to 336 MB resident in Ollama, a second server dependency. Limitations: small n, Claude-authored labels, untuned RRF, dev only.

## Recommendation (for the owner; the Decision field above is left blank)
**No-go on embeddings and hybrid fusion in the retrieval path; keep BM25 + graph (option A).** Not selected on one metric: recall, precision, MRR, nDCG, localisation and evidence coverage on dev favour G; cost, latency, memory and maintainability add burden without a measured benefit. P5-S09 (reranking) and P5-S11 (needs owner spend approval) are not unlocked by this evidence. If hybrid had improved retrieval, adoption would still need (not run): a new fingerprinted release candidate, preregistered downstream diagnosis and repair on a harder case set with replicates and approved spend, a no-leak check of the index, and a fix of `OllamaEmbedder` to use 127.0.0.1 (done: it now defaults to 127.0.0.1; `localhost` cost about 2 s per call here). A narrow dense fallback for identifier-free queries is a new, unsupported hypothesis. Status stays PROPOSED; D36 and Q16 carry status notes only. Provenance: Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; tasks P5-S06..S09 and S12..S16 stay Rafique's. Retrieval-level evidence only: downstream diagnosis and repair were not tested with embeddings.

## How to revert
Delete the new retrieval modules and `results/retrieval/`; nothing frozen was edited, so RC1 is unaffected.

## Status check 2026-11-25 (updated)
Still PROPOSED and **no decision recorded** (the Decision section above stays blank). P5-S06 and P5-S07 are IMPLEMENTED and TESTED; P5-S08 is DONE with a preregistered NO-GO (see Outcome and Recommendation above); P5-S09 is NOT STARTED and NOT TRIGGERED; P5-S11 (Ruhan's) is conditional, gate not met. Local models ran through Ollama (all-minilm:22m, nomic-embed-text, jina-embeddings-v2-base-code community build). The dense/hybrid code remains an opt-in research module (`traceforge/retrieval_next`); nothing in the product path imports embedding code. Traversal/impact addendum: P5-S12 ranker preregistered NO-GO, P5-S15 GO on fixtures, P5-S16 reduced suite implemented, P5-S13/S14 not started; the decision for that addendum is also blank. Local suite 1,120 passed, 36 deselected; CI green on dd3fae2.
