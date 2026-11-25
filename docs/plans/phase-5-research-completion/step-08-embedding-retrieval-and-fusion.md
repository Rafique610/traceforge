# P5-S08 — Embedding retrieval (RET-E), fusion arms and ADR 0003

Follow-up study **Retrieval modernization** (added 2026-11-24). Design: [retrieval-architecture-review.md](../../research/retrieval-architecture-review.md) sections 2.2, 2.5, 5. Decision D36; assumption AS11; open question Q16. Conditional on frozen RC1 staying untouched; zero AxForge tokens.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 8 |
| Task ID | P5-S08 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | ESSENTIAL (decision gate) |
| Effort | 2 days plus model setup (design doc: dense retriever 1 to 1.5, fusion and ablations 0.5 to 1) |
| Status | DONE with a preregistered NO-GO (not reviewed, not approved; ADR 0003 PROPOSED, decision blank) |
| Branch | none (commit on `main`, D33) |

**Status sync 2026-11-25.** Evidence: `traceforge/retrieval_next` (opt-in research module), `docs/research/embedding-hybrid-evaluation.md` and `-preregistration.md`. Models run: all-minilm:22m (45 MB, 384-d, ctx 512), nomic-embed-text (274 MB, 768-d, ctx 2048), jina-embeddings-v2-base-code community build (322 MB, 768-d, ctx 8192; primary). 31 of 33 dev cases scored (2 have no retrieval target) plus 45 benchmark queries. At an equal 3000-token budget on dev, G beats G+E and E alone (packed coverage G 0.919, LGE 0.806, E 0.581); on 45 free-text queries the fused arms are nominally ahead (Recall@10 0.607 vs 0.556), CI includes 0. H1 FAIL (-0.094 [-0.188, 0.000]), H2 FAIL (loss 0.133), H3 FAIL (-0.004), H4 PASS (E MRR 0.384 vs BM25 0.746). Recommendation: keep BM25 + graph; embeddings not adopted. Retrieval-level evidence only; downstream diagnosis/repair not tested with embeddings. Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; the task stays Rafique's.

## B. Objective
Evaluate dense retrieval and fusion offline on the dev split and deliver **ADR 0003 "Retrieval architecture decision"**: go / no-go for embeddings and hybrid retrieval, decided by preregistered thresholds.

## C. Prerequisites
- P5-S06 (baselines, scorer) and P5-S07 (embedding cache, manifest).
- Owner approval of the embedding model (Q16) and confirmation that it runs locally (AS11: the Ollama server was not responding, torch and sentence-transformers are absent). Any install goes to D: (C: has about 3 GB free). No hosted embeddings in the experiment.

## D. Technical background
- Arms (review section 5): RET-E (dense top-50, same query text as BM25), RET-LE (RRF k = 60 of BM25 and dense), RET-LG (current G), RET-LGE (RRF of the G ranking and dense); forced anchors first as today. Baselines RET-L / RET-G come from P5-S06.
- Model candidates: all-MiniLM-L6-v2 (general baseline) and one small code-trained model (CodeRankEmbed 137M or jina-embeddings-v2-base-code 161M). No 1.5B to 7B models.
- **Graph decision ADR:** P5-S01 and P5-S03 require a "graph decision ADR" that does not exist (known inconsistency 7). **ADR 0003 is proposed to satisfy that prerequisite, subject to project-owner approval**; nothing here marks it accepted.

## E. Implementation instructions
1. Preregister before any run (commit the file first): hypotheses H1 to H4 and thresholds from review section 5.4 (H1: fused arm raises gold-in-packed-context recall on dev configuration cases over G by >= 0.15 absolute; H2: no application_code loss beyond 0.05; H3: precision at equal tokens >= G; H4: E alone worse than BM25 on identifier-heavy queries). k in {30, 60}, one run each, no tuning loops.
2. New modules `retrieval/dense.py` and `retrieval/hybrid.py` using the P5-S07 store; not imported by any frozen file.
3. Run all arms through the P5-S06 harness at equal budget (3000 tokens, 2400 usable) plus budget-matched L/G, ablations (E alone, L+E, G+E), with and without dedup, per cause class, paired bootstrap CIs.
4. Record model id, revision, dims, preprocessing version, batch size, seeds, package versions; CPU, float32; two runs give identical rankings.
5. Write ADR 0003 (status PROPOSED) with the measured outcome and a go/no-go recommendation; update D36 and Q16 only after owner approval.

## F. Checklist
- [ ] Embedding model approved and verified runnable (AS11 closed or changed)
- [ ] Preregistration committed before the first run
- [ ] RET-E, RET-LE, RET-LG, RET-LGE results on dev at equal budget
- [ ] Ablations, budget-matched baselines, CIs, per-class tables
- [ ] Contamination checks; fingerprint unchanged
- [ ] ADR 0003 finalized (still PROPOSED) with go/no-go
- [ ] Owner decision recorded

## G. Expected deliverables
`dense.py`, `hybrid.py`, preregistration file, `results/retrieval/<run_id>/` tables, `docs/adrs/0003-retrieval-architecture-decision.md`.

## H. Testing and validation
- Unit: RRF on fixed lists (hand-computed), forced anchors stay first, deterministic ties, dims mismatch raises.
- Fairness: `GraphFeatures` all off equals L; fused arms use the same `pack()` and budget.
- Acceptance: every preregistered threshold reported pass/fail with CIs; go requires H1 and H2 to hold on dev, otherwise ADR 0003 recommends no-go and the study stops; 0 tokens; fingerprint unchanged.

## I. Dependencies and integration
- **Informed by:** retrieval-architecture-review.md sections 2 and 5; D18 (embeddings optional).
- **Depends on:** P5-S06, P5-S07 (and owner approval of the model, Q16).
- **Unblocks:** P5-S09 and P5-S11 (go only); the graph-decision-ADR prerequisite of P5-S01 / P5-S03 (if the owner approves ADR 0003).

## J. Definition of done
ADR 0003 reviewed by Ruhan and approved or rejected by the owner; results reproducible from saved runs.
