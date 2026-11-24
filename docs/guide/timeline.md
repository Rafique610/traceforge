# Timeline

> **Status sync 2026-11-25.** This chapter was written on 2026-11-21 and parts are historical. Current status of Ruhan's 20 primary tasks: **none COMPLETE & VERIFIED**; 11 IMPLEMENTED NOT VERIFIED, 7 PARTIALLY COMPLETE, 2 NOT STARTED (conditional). Nothing is reviewed by Rafique or approved by the owner. Authoritative: `docs/plans/RUHAN_TASK_TRACKER.md`. Where this chapter says Rafique's components are absent, there is no experiment, or the model is undecided, that is stale: the lab, sandbox, evidence, graph, retrieval, metrics and a 184-case frozen dataset exist; a reduced RC1 evaluation exists in `results/final` (35 sites at replicate 0, 12 at replicate 1, 8 at replicate 2; AxForge `glm-5.3-flash`); the team is two members (Rafique, Ruhan).


Back to [TraceForge Explained](TraceForge-Explained.md). Only dated facts found in the repo are listed. The history before 2026-11-21 (proposal, early commits) is **not recorded in the files I read**; `git log` was not available in this working tree check, so earlier dates are left out rather than guessed.

## Known dates

| Date | Event | Source |
|---|---|---|
| Before 2026-11-21 | Phase 0 foundation: backend skeleton (`/health`, Postgres, Alembic, Taskfile) and the contracts with samples were on `main` (commit `839a62d`) | `docs/domain/traceforge/index.md`, handoff note |
| 2026-11-20 | Timestamp inside the sample evidence (`2026-11-20 10:14:03`). This is sample data, not a project event | `contracts/samples/evidence_bundle.config.json` |
| 2026-11-21 | Feasibility review: design choices recorded (ripgrep baseline, search/replace edits, measured context cap, code map in both arms, validity guards) | `docs/domain/traceforge/index.md` |
| 2026-11-21 | Rafique's retrieval spike report (Part A) exists | `docs/research/limits-report.md` |
| 2026-11-21 | Stage A handoff written; machine resources measured (`C:` 91% full) | `.memory/21-november-2026/stage-a-handoff.md` (git-ignored) |
| 2026-11-21 | Stage B work on local branch `ruhan/stage-b-work` (decisions B1-B5) | `docs/orchestration/DECISIONS.md` |
| 2026-11-21 | Implemented in the working tree: frontend scaffold (P0-S03), incidents API and DB (P1-S04), model gateway (P1-S05); free-provider research written | `STATE.md`, `RUHAN_CHECKLIST.md` |
| 2026-11-21 | Pipeline agent (P1-S06) and repair core (P2-S04 policy/worktree/loop) code and tests present in the tree | files under `agent/`, `repair/`, `tests/` (checklist still lists them as not started: **checklist is behind the code**) |
| 2026-11-21 | Problems P-001 to P-005 met and handled (see [problem log](problem-log.md)) | session report |

Progress claim in `docs/plans/RUHAN_CHECKLIST.md`: **0 / 20 steps verified** (verification requires the owner's approval). Steps in NEEDS REVIEW at that time: P0-S03, P1-S04, P1-S05 (partial), P0-S05 confirmation.

## Plan phases (from `docs/plans/README.md` as summarized in the domain page): 7 phases, 36 steps

| Phase | Theme | State |
|---|---|---|
| 0 | Foundation (repo, backend and frontend scaffolds, proposal approval, contracts, feasibility prototype) | In progress |
| 1 | Core components (lab, sandbox, fault generator, incidents, gateway, pipeline agent, Sync 1) | Ruhan's P1-S04, S05 implemented; S06 code exists; S07 blocked on Rafique's P1-S03 |
| 2 | Evidence to repair (evidence, graph, retrieval, repair loop, report and review, GitHub intake, Sync 2) | Repair core present (fake runner); the rest Planned or Rafique's |
| 3 | Dataset, evaluation, reviewer UI | Planned |
| 4 | A3 delivery (first experiments, demo pack) | Planned |
| 5 | Research completion (full 2x2 x 3 replicates, model sensitivity, BugsInPy subset) | Planned |
| 6 | Productization and paper (security hardening, CI and deployment, UI polish, paper) | Planned |

## Pending right now (all marked pending)

- Owner review and approval of implemented steps (only Ruhan approves).
- Integration of agent outputs into shared files: Taskfile, README, config (STATE.md "Next").
- Model probe (P0-S06 Part B) once a model is usable; ADR 0001.
- P2-S04 integration against Rafique's sandbox; until then a fake runner.
- Q3: conditional written permission received 18 Nov (email on disk); written confirmation of the revised proposal still open. Provider sign-ins (human step).
- Rafique's tracks: P1-S02 sandbox, P1-S03 seed cases, P2-S01..03 evidence/graph/retrieval, P3-S01/02 dataset and metrics.
- Update README and `docs/plans/TEAM_WORK_DISTRIBUTION.md` section 0 before any commit (process rule), after approval.

## Later dates (added 2026-11-25)
| Date | Event | Source |
|---|---|---|
| 2026-11-22 | Model switched to AxForge `glm-5.3-flash` (owner decision B17) | `docs/adrs/0001-primary-model.md` |
| 2026-11-23 | Frozen dataset approved by Rafique (184 validated: test 151, dev 33); revised proposal PDF dated 23 Nov exists outside the repo | `docs/plans/TEAM_WORK_DISTRIBUTION.md`; `D:\TraceForge\proposal` |
| 2026-11-24 | RC1 frozen; reduced final evaluation (35 sites); second key slot; RC1 stage-2 report | `docs/DEV_LOG.md`, `docs/research/final-evaluation-stage2.md` |
| 2026-11-25 | `POST /incidents/{id}/investigate`, Sync 1 integration test, RC2 opt-in files (not validated), hw_monitor, local-model smoke (failed with HTTP 400), CI workflow authored (no GitHub run), status sync of all Ruhan documents | `docs/DEV_LOG.md` |
