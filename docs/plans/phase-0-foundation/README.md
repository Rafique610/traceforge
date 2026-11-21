# Phase 0 — Foundation

**Status:** IN PROGRESS (P0-S02 COMPLETED; P0-S01 nearly done; P0-S05 waits on Ruhan's field check; P0-S06 Part A done, Part B not started; P0-S03, P0-S04 NOT STARTED)

## Phase information
- **Purpose:** give both members a running skeleton, the shared contracts, and an approved scope, so Phase 1 can run fully in parallel.
- **Objectives:** collaborators in place; backend and frontend start with one command; five contracts merged with samples; revised proposal sent for explicit approval.
- **Scope:** repo access, scaffolds, contracts, proposal. No feature code.
- **Expected outcome:** milestone **M0**.
- **Prerequisites:** repo exists (done), docs tree (done), Synverk board (done).

## Task overview
| Step ID | Task | Responsible | Dependencies | Status |
|---|---|---|---|---|
| [P0-S01](step-01-repository-and-collaboration-setup.md) | Repository and collaboration setup | Rafique | — | IN PROGRESS |
| [P0-S02](step-02-backend-scaffold.md) | Backend scaffold (TRAC-1) | Rafique | P0-S01 | COMPLETED |
| [P0-S03](step-03-frontend-scaffold.md) | Frontend scaffold (TRAC-2) | Ruhan | P0-S01 | NOT STARTED |
| [P0-S04](step-04-proposal-update-and-approval.md) | Proposal update and approval (TRAC-3) | Ruhan | — | NOT STARTED |
| [P0-S05](step-05-shared-contracts.md) | Shared contracts + samples (TRAC-4) | Rafique (+Ruhan) | P0-S02 | NEEDS REVIEW |
| [P0-S06](step-06-feasibility-prototype.md) | Feasibility prototype: retrieval spike (A) + model probe (B) | Rafique (A) + Ruhan (B) | P0-S02 | IN PROGRESS (Part A done) |

## Execution order
1. **P0-S01 first** (Rafique): until Ruhan is a collaborator he cannot push.
2. **In parallel:** P0-S02 (Rafique) ‖ P0-S03 and P0-S04 (Ruhan).
3. **P0-S05** after P0-S02 merges (contracts live in the backend package). Pair session.
4. **P0-S06** after P0-S02, both in parallel (2 days each). Its limits report confirms D19–D21 before P1-S05, P1-S06, P2-S03 and P2-S04 start.
- Blocking: P0-S01 blocks all merges; P0-S02 blocks P0-S05, P1-S01, P1-S05; P0-S05 blocks P1-S02, P1-S04, P2-S01, P3-S02.
- Cross-member: P0-S03 adds Taskfile entries to the file P0-S02 creates, so whoever merges second rebases.

## Deliverables
- Ruhan with write access; `main` protection verified; PR #1 merged.
- `backend/` uv project with `/health`, Postgres in Compose, Alembic, Taskfile, ruff, pytest.
- `frontend/` Vite app showing API health.
- `backend/traceforge/contracts/` with 5 contracts + samples + tests.
- Revised proposal PDF sent; approval reply saved.
- `docs/research/limits-report.md` with real numbers from the retrieval spike and model probe.

## Completion criteria
- [ ] `task dev`, `task test`, `task lint`, `task web`, `task web:test` succeed on **both** laptops.
- [ ] All contract samples validate; PR approved by both.
- [ ] Revised proposal sent; reply saved (or logged as awaiting).
- [ ] No credential in any tracked file (`git grep` check in P0-S02).
- [ ] Limits report written; D19–D21 confirmed or revised.

## Handoff to Phase 1
- Rafique → Ruhan: how to run the backend; where `Settings` lives; how to add a router.
- Both: contract samples are the stand-ins until real producers exist ([INTEGRATION_PLAN.md](../INTEGRATION_PLAN.md#interfaces-between-modules-function-level)).
- Ruhan → both: supervisor feedback on the revised scope, if any changes are requested.

## Navigation
- [P0-S01 Repository and collaboration setup](step-01-repository-and-collaboration-setup.md)
- [P0-S02 Backend scaffold](step-02-backend-scaffold.md)
- [P0-S03 Frontend scaffold](step-03-frontend-scaffold.md)
- [P0-S04 Proposal update and approval](step-04-proposal-update-and-approval.md)
- [P0-S05 Shared contracts](step-05-shared-contracts.md)
- [P0-S06 Feasibility prototype](step-06-feasibility-prototype.md)
- Back to [plans README](../README.md) · Next: [Phase 1](../phase-1-core-components/README.md)
