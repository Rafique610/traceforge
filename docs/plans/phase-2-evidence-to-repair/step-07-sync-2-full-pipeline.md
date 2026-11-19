# P2-S07 — Sync 2: full pipeline end to end

## A. Task identification
| Field | Value |
|---|---|
| Phase | 2 Evidence-to-repair |
| Step | 7 |
| Task ID | P2-S07 |
| Synverk card | TRAC-18 |
| Primary owner | Muhammad Rafique |
| Supporting | Muhammad Ruhan Kamran (agent wiring) |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Normal (critical path) |
| Effort | 1 day (joint) |
| Status | NOT STARTED |
| Branch | `rafique/P2-S07-sync-2` |

## B. Objective
Everything real, nothing sampled: broken lab → evidence → graph + retrieval → agent → repair with hidden tests → report → review. This proves the architecture works before the dataset is scaled.

## C. Prerequisites
- P2-S01, P2-S02, P2-S03 (Rafique); P2-S04, P2-S05 (Ruhan). P2-S06 is not required here.

## D. Technical background
The agent's `EvidenceSource`/`ContextSource` interfaces get real implementations (`LabEvidenceSource`, `RetrievalContextSource(mode)`); `get_neighbors` gets the real graph. Pipeline code should not change otherwise. `POST /incidents/{id}/investigate` starts the pipeline as a FastAPI background task.

## E. Implementation instructions
1. Ruhan adds `LabEvidenceSource` and `RetrievalContextSource` behind the existing protocols, and wires `get_neighbors` to `codeintel`.
2. Add `POST /incidents/{id}/investigate` (background task, idempotent: second call while running → 409).
3. `task pipeline:run CASES=seed CONDITIONS=L0,G0`: for each seed case, apply it to the lab, create an incident, investigate, collect the record, restore the lab.
4. Expected outcomes: config and code cases verified (or an explained model failure); runtime_dependency → diagnosis with no patch; insufficient_evidence → abstain.
5. Record LLM responses once live, then add `tests/integration/test_pipeline_e2e.py` replaying from cache (offline, free).
6. Both run `task pipeline:run` on their own laptop.
7. List every break observed (feeds the failure taxonomy in P4-S02); fix in the owning lane; contract changes via contract PR.
8. Record a Synverk proof with screenshots of the API responses.

## F. Checklist
- [ ] Real sources wired; graph tool live
- [ ] Investigate endpoint (background, idempotent)
- [ ] `pipeline:run` task with lab apply/restore
- [ ] 4 seed cases × L0, G0 run live
- [ ] Outcomes match expectations or are explained
- [ ] E2E test replaying from cache
- [ ] Runs on both laptops
- [ ] Break list posted on TRAC-18
- [ ] Synverk proof recorded

## G. Expected deliverables
New: real source adapters, investigate endpoint, `pipeline:run` task, `tests/integration/test_pipeline_e2e.py`. Run records in `runs/dev/`.

## H. Testing and validation
- E2E test passes offline.
- Acceptance: 8 records (4 cases × 2 conditions), all schema-valid; correct outcome class for decoy and abstain cases.

## I. Dependencies and integration
- **Depends on:** P2-S03, P2-S04, P2-S05.
- **Unblocks:** P3-S04 (runner on real pipeline), P4-S01.

## J. Definition of done
E2E test merged; both laptops ran the full pipeline; break list posted; TRAC-18 approved.
