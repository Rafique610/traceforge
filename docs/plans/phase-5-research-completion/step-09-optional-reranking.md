# P5-S09 — Optional reranking (cross-encoder or fusion-weight tuning)

Follow-up study **Retrieval modernization** (added 2026-11-24). Design: [retrieval-architecture-review.md](../../research/retrieval-architecture-review.md) section 2.5. **OPTIONAL**: drop first if time is short. Zero AxForge tokens.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 9 |
| Task ID | P5-S09 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | OPTIONAL |
| Effort | 1 day (design doc) |
| Status | NOT STARTED, NOT TRIGGERED (conditional on a P5-S08 go; S08 was no-go) |
| Branch | none (commit on `main`, D33) |

**Status sync 2026-11-25.** Evidence: P5-S08 finished as a preregistered NO-GO; no code exists. Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; the task stays Rafique's.

## B. Objective
Only if P5-S08 recommends go and shows recall gains but weak ranking: test a CPU cross-encoder rerank (RET-LE+R, RET-LGE+R over the same top-50) or fusion-weight tuning, tuned on **dev only**.

## C. Prerequisites
P5-S08 go decision (owner approved). No LLM rerank (it uses provider tokens and is out of scope).

## D. Technical background
Cost is candidates x chunk tokens per query (about 20k tokens of CPU inference for 50 x 400, ASSUMPTION). Small cross-encoders are not code-specific. Preregister thresholds before running; any tuning is reported with its dev-only caveat.

## E. Implementation instructions
1. New module `retrieval/rerank.py`, not imported by frozen files.
2. Run through the P5-S06 harness at equal budget; report against RET-LE / RET-LGE and the budget-matched baselines.
3. Record latency per query and model size; add an addendum to ADR 0003 (still subject to owner approval).

## F. Checklist
- [ ] P5-S08 go recorded
- [ ] Preregistration committed
- [ ] Rerank arms evaluated with CIs and latency
- [ ] ADR 0003 addendum, or an explicit drop note

## G. Expected deliverables
`rerank.py`, results under `results/retrieval/`, ADR addendum, or a dated drop note in DECISIONS_AND_OPEN_QUESTIONS.

## H. Testing and validation
Deterministic ordering on fixed candidates; rerank never drops forced anchors; fingerprint `ee3d8d87...` unchanged. Acceptance: improvement shown with paired CIs at equal tokens, or the step is dropped.

## I. Dependencies and integration
- **Informed by:** review section 2.5.
- **Depends on:** P5-S08 go.
- **Unblocks:** optional input to P5-S11.

## J. Definition of done
Evaluated and reviewed, or explicitly dropped with a note (as for P5-S05).
