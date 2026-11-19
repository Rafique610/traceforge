# Phase 2 — Evidence-to-repair pipeline

**Status:** NOT STARTED

## Phase information
- **Purpose:** replace every sample with the real thing: real evidence from the lab, the code graph, retrieval in both modes, the repair loop with independent verification, the report and review, and the GitHub integration.
- **Objectives:** one command takes a seed case from a broken lab to a verified (or honestly unverified) patch and a stored review, with real evidence and context.
- **Scope:** pipeline correctness on the 4 seed cases. Dataset scale, UI and experiments are Phase 3.
- **Expected outcome:** milestone **M2 (Sync 2)**.
- **Prerequisites:** M1.

## Task overview
| Step ID | Task | Responsible | Dependencies | Status |
|---|---|---|---|---|
| [P2-S01](step-01-evidence-collector.md) | Evidence collector (TRAC-12) | Rafique | P0-S05, P1-S01 | NOT STARTED |
| [P2-S02](step-02-code-graph.md) | Code graph (TRAC-13) | Rafique | P1-S01 | NOT STARTED |
| [P2-S03](step-03-retrieval-l-and-g.md) | Retrieval L and G + E1 (TRAC-14) | Rafique | P2-S01, P2-S02 | NOT STARTED |
| [P2-S04](step-04-repair-loop.md) | Repair loop (TRAC-15) | Ruhan | P1-S02, P1-S06 | NOT STARTED |
| [P2-S05](step-05-report-and-review.md) | Report and review (TRAC-16) | Ruhan | P1-S04, P2-S04 | NOT STARTED |
| [P2-S06](step-06-github-intake.md) | GitHub intake (TRAC-17) | Ruhan | P1-S04 | NOT STARTED |
| [P2-S07](step-07-sync-2-full-pipeline.md) | Sync 2 (TRAC-18) | Rafique (+Ruhan) | P2-S03, P2-S04, P2-S05 | NOT STARTED |

## Execution order
- **Track A:** P2-S01 and P2-S02 can run in either order (or interleaved); P2-S03 needs both. This lane is the **critical path**.
- **Track B:** P2-S04 → P2-S05; P2-S06 is independent (can be done first or in a gap). Ruhan has ~3 days of slack here: use it to start P3-S03 (UI) against samples.
- **Join:** P2-S07.

## Deliverables
`evidence/`, `codeintel/`, `retrieval/`, `repair/`, `reports/`, `reviews/`, `github/` modules; E1 retrieval eval CLI; no-leak test; end-to-end integration test from cache.

## Completion criteria
- [ ] Evidence for each seed case shows the symptom; redaction test passes
- [ ] Graph built for the lab with every edge type tested; `distance()` recomputed for seed cases
- [ ] `task eval:retrieval` prints L vs G by distance
- [ ] Seed config and code cases reach `TEST_VERIFIED_IN_LAB` (or documented failure); hidden-test no-leak test passes
- [ ] Report and hash-bound review work; tampered hash rejected
- [ ] A real GitHub issue creates an incident
- [ ] One command runs all 4 cases end to end on both laptops

## Handoff to Phase 3
- Rafique → Ruhan: real `retrieve()` and `collect()` signatures and their runtime cost.
- Ruhan → Rafique: real `AgentRunRecord`s from Sync 2 to build metrics on.
- Both: the list of failure modes seen at Sync 2 (seeds P4-S02's taxonomy).

## Navigation
- [P2-S01 Evidence collector](step-01-evidence-collector.md)
- [P2-S02 Code graph](step-02-code-graph.md)
- [P2-S03 Retrieval L and G](step-03-retrieval-l-and-g.md)
- [P2-S04 Repair loop](step-04-repair-loop.md)
- [P2-S05 Report and review](step-05-report-and-review.md)
- [P2-S06 GitHub intake](step-06-github-intake.md)
- [P2-S07 Sync 2](step-07-sync-2-full-pipeline.md)
- Previous: [Phase 1](../phase-1-core-components/README.md) · Next: [Phase 3](../phase-3-dataset-evaluation-ui/README.md) · [Plans README](../README.md)
