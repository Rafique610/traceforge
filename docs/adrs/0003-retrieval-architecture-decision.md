# ADR 0003: Retrieval architecture decision

Status: PROPOSED (not accepted; needs project-owner approval)
Steps: P5-S06, P5-S07, P5-S08 (deliverable). Proposed to satisfy the "graph decision ADR" prerequisite of P5-S01 and P5-S03.
Design: [retrieval-architecture-review.md](../research/retrieval-architecture-review.md). Decision D36, assumption AS11, question Q16.

## Context
Retrieval is BM25 over graph-derived chunks (L) plus a 2-hop graph walk (G). No embeddings exist (verified 24 Nov 2026). RC1 (fingerprint `ee3d8d87...`) is frozen. Frozen-set offline recall in the sent context is 23/29 (L) and 24/29 (G); exact diagnosis was 28 to 29 of 29, so the benchmark is near saturation. Embedding availability on the machine is unconfirmed (AS11).

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
- Go: P5-S09 (optional) and P5-S11 (needs owner spend approval) may start; embedding code stays in new modules outside the fingerprint list; any wiring into a frozen condition needs a new fingerprinted release candidate.
- No-go: embeddings are dropped from P2-S03's open checklist item; manifest and cache code from P5-S07 remains available.
- If the owner accepts this ADR, it also satisfies the graph-decision prerequisite of P5-S01 / P5-S03 only to the extent it records whether graph changes enter the main experiment (the A3 graph stays frozen by default).

## PROPOSED addendum (25 Nov 2026): decision gate for traversal and impact capabilities
Design: [root-cause-impact-regression-design.md](../research/root-cause-impact-regression-design.md). Decision D37 (proposed), assumption AS12, questions Q17 and Q18. Tasks P5-S12 to P5-S17 add an overlay with evidence classes, bidirectional traversal and ranking, a change-impact report with visible-test selection, and a conditional regression-aware repair validation (RC2 only). Gate: the capabilities are kept only if the thresholds preregistered in P5-S16 pass on hand-verified fixtures; Tier 2 (P5-S13, P5-S14) and P5-S17 only after the MVP shows a measurable gain and the owner approves. **Decision: none yet** (blank). Nothing here changes RC1.

## How to revert
Delete the new retrieval modules and `results/retrieval/`; nothing frozen was edited, so RC1 is unaffected.

## Status check 2026-11-25
Still PROPOSED and **no decision recorded** (the Decision section above stays blank). P5-S06, P5-S07 and P5-S08 are NOT STARTED, so none of the preregistered thresholds has a result. A local embedding model does run (all-minilm:22m, 384-d; first call 23 s including model load), but a code-specific embedding model is not downloaded (Rafique's decision). Nothing in the product path imports embedding code.

