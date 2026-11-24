# P1-S07 — Sync 1: agent on the 4 real seed cases

## A. Task identification
| Field | Value |
|---|---|
| Phase | 1 Core components |
| Step | 7 |
| Task ID | P1-S07 |
| Synverk card | TRAC-11 |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | Muhammad Rafique |
| Reviewer | Muhammad Rafique |
| Priority | Normal |
| Effort | 0.5 day (joint session) |
| Status | IMPLEMENTED, TESTED, NOT REVIEWED/APPROVED |
| Branch | `ruhan/P1-S07-sync-1` |

**Status sync 2026-11-25.** Evidence: `pytest tests/integration` 7 passed (`test_sync1.py`, fake gateway, offline replay of `ManifestCaseSource`; route, pipeline, repair, report, review). Both members still need to run it on their own machines. The old 'blocked on P1-S03' is stale: P1-S03 is complete. Five-fact detail: `docs/plans/RUHAN_TASK_TRACKER.md`.

## B. Objective
First join of the two tracks: the agent reads Rafique's real `CaseManifest`s (evidence and context still from samples). Catches contract mismatches while they are cheap to fix.

## C. Prerequisites
- P1-S03 (4 validated seed cases), P1-S06 (agent on samples).
- Both members available.

## D. Technical background
Only the case source changes; evidence/context remain samples, so failures here are about manifests and paths, not retrieval quality.

## E. Implementation instructions
1. Add `ManifestCaseSource` reading `datasets/manifests/dev.jsonl`.
2. Point `task agent:run` at a manifest `case_id` (e.g. `CASE=code-shop_api-001`).
3. Run all 4 seed cases with condition L0 on Mistral (and once on Ollama to check the comparator path works).
4. For each failure, decide: contract issue (→ contract PR, both approve), agent bug (Ruhan fixes), manifest bug (Rafique fixes).
5. Add `tests/integration/test_sync1.py`: runs the 4 cases from cached LLM responses (record once live, replay after).
6. Record a Synverk proof: steps run, records produced.

## F. Checklist
- [ ] `ManifestCaseSource`
- [ ] 4 cases run live on Mistral
- [ ] Comparator path smoke-run on Ollama
- [ ] Mismatches triaged and fixed in the right lane
- [ ] Integration test replaying from cache
- [ ] Synverk proof recorded; results commented on TRAC-11

## G. Expected deliverables
New: `agent/sources.py` addition, `tests/integration/test_sync1.py`, 4 records under `runs/dev/` (git-ignored; summary pasted on the card). Possibly a contract PR.

## H. Testing and validation
- 4 schema-valid records. Outcome correctness is **not** required yet (evidence is still sample data); validity and no crashes are.
- The integration test passes offline.

## I. Dependencies and integration
- **Depends on:** P1-S03, P1-S06.
- **Unblocks:** P2-S04 testing on real cases; confidence for Phase 2 interfaces.

## J. Definition of done
Integration test merged; both members ran it on their laptops; any contract change merged; TRAC-11 approved.
