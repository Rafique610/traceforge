# P5-S11 — Conditional end-to-end hybrid experiment

Added 2026-11-24. Design: [retrieval-architecture-review.md](../../research/retrieval-architecture-review.md) section 5.6 and [technical-findings-2026-11-24.md](../../research/technical-findings-2026-11-24.md) section 7B. **CONDITIONAL**: runs only if P5-S08 decides go.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 11 |
| Task ID | P5-S11 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | Muhammad Rafique (retrieval wiring) |
| Reviewer | Muhammad Rafique |
| Priority | CONDITIONAL |
| Effort | 2 days plus unattended runs (planning estimate, AS1) |
| Status | NOT STARTED (conditional on P5-S08 go) |
| Branch | none (commit on `main`, D33) |

**Status sync 2026-11-25.** Unchanged. Five-fact detail: `docs/plans/RUHAN_TASK_TRACKER.md`.

## B. Objective
Run new conditions (H0/H1 or the chosen RET arms) through the diagnosis and patch pipeline on unseen cases, in new run directories, to see whether an offline retrieval gain carries to verified repair. RC1 conditions and artifacts stay untouched.

## C. Prerequisites
- P5-S08 go (ADR 0003 approved by the owner); P5-S10 if the RC2 changes are included.
- **Owner approval for any AxForge spend** (Q16); small token budget. The benchmark is near saturation (28 to 29 of 29), so a harder or fresh case set is recommended before spending tokens.

## D. Technical background
New condition names and runner config; wiring through new modules (no edits to frozen retrieval files unless a new RC is declared and fingerprinted); same safeguards (leak guard, frozen split hash, pacing, ledger). Preregister hypotheses, the seeded case draw (recorded before any call), replicates and the token ceiling.

## E. Implementation instructions
1. Preregistration and token budget approved by the owner.
2. Rafique provides the retrieval wiring (dense index at the case base commit, fused arm); Ruhan adds conditions and runs them with the existing runner.
3. The 35 analysed sites are never used as confirmation; new run directories only.

## F. Checklist
- [ ] P5-S08 go and owner spend approval recorded
- [ ] Preregistration and token ceiling
- [ ] Conditions and wiring reviewed
- [ ] Runs complete with the ledger within the ceiling
- [ ] Analysis with paired CIs; limitations stated

## G. Expected deliverables
Condition files, run directories, analysis note; no change to `results/final`.

## H. Testing and validation
Fake-gateway pipeline test with the fused arm; RC1 fingerprint unchanged (or RC2 recorded); the ledger refuses to cross the ceiling. Acceptance: results reproducible from saved runs.

## I. Dependencies and integration
- **Informed by:** ADR 0003, P5-S09 (optional).
- **Depends on:** P5-S08 go (+ P5-S10 if included).
- **Unblocks:** paper discussion (P6-S04) as follow-up work.

## J. Definition of done
Executed and reviewed, or explicitly not started because P5-S08 said no-go (note in DECISIONS_AND_OPEN_QUESTIONS).
