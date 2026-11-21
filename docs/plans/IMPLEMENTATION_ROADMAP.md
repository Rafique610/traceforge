# Implementation roadmap

From the current state (repo + docs + board, no code) to the final Assignment 4 deliverable. Owners match [TEAM_WORK_DISTRIBUTION.md](TEAM_WORK_DISTRIBUTION.md). All tasks are **NOT STARTED** except P0-S01 (IN PROGRESS).

## Task-to-card map
| ID | Task | Card | Owner | Reviewer | Depends on | Effort (d) | Status |
|---|---|---|---|---|---|---|---|
| P0-S01 | Repository and collaboration setup | — | Rafique | Ruhan | — | 0.5 | IN PROGRESS |
| P0-S02 | Backend scaffold | TRAC-1 | Rafique | Ruhan | P0-S01 | 1 | COMPLETED |
| P0-S03 | Frontend scaffold | TRAC-2 | Ruhan | Rafique | P0-S01 | 1 | NOT STARTED |
| P0-S04 | Proposal update and supervisor approval | TRAC-3 | Ruhan | Rafique | — | 1 | NOT STARTED |
| P0-S05 | Shared contracts + samples | TRAC-4 | Rafique (+Ruhan) | Both | P0-S02 | 1 | NEEDS REVIEW |
| P0-S06 | Feasibility prototype (retrieval spike + model probe) | — | Rafique (A) + Ruhan (B) | optional | P0-S02 | 2 + 2 | IN PROGRESS (A done) |
| P1-S01 | Lab fixtures | TRAC-5 | Rafique | Ruhan | P0-S02 | 2.5 | NOT STARTED |
| P1-S02 | Sandbox test runner | TRAC-6 | Rafique | Ruhan | P0-S05 | 2 | NOT STARTED |
| P1-S03 | Fault generator + 4 seed cases | TRAC-7 | Rafique | Ruhan | P1-S01, P1-S02 | 3 | NOT STARTED |
| P1-S04 | Incidents API + DB | TRAC-8 | Ruhan | Rafique | P0-S05 | 2 | NOT STARTED |
| P1-S05 | Model gateway + cache + ADR 0001 | TRAC-9 | Ruhan | Rafique | P0-S02 | 2 | NOT STARTED |
| P1-S06 | Pipeline agent | TRAC-10 | Ruhan | Rafique | P1-S04, P1-S05 | 3 | NOT STARTED |
| P1-S07 | Sync 1: agent on real seed cases | TRAC-11 | Ruhan (+Rafique) | Rafique | P1-S03, P1-S06 | 0.5 | NOT STARTED |
| P2-S01 | Evidence collector | TRAC-12 | Rafique | Ruhan | P0-S05, P1-S01 | 2.5 | NOT STARTED |
| P2-S02 | Code graph | TRAC-13 | Rafique | Ruhan | P1-S01 | 3 | NOT STARTED |
| P2-S03 | Retrieval L and G + E1 | TRAC-14 | Rafique | Ruhan | P2-S01, P2-S02 | 3 | NOT STARTED |
| P2-S04 | Repair loop | TRAC-15 | Ruhan | Rafique | P1-S02, P1-S06 | 3.5 | NOT STARTED |
| P2-S05 | Report and review | TRAC-16 | Ruhan | Rafique | P1-S04, P2-S04 | 1.5 | NOT STARTED |
| P2-S06 | GitHub intake | TRAC-17 | Ruhan | Rafique | P1-S04 | 1.5 | NOT STARTED |
| P2-S07 | Sync 2: full pipeline | TRAC-18 | Rafique (+Ruhan) | Ruhan | P2-S03, P2-S04, P2-S05 | 1 | NOT STARTED |
| P3-S01 | Dataset scale-up and freeze | TRAC-19 | Rafique | Ruhan | P1-S03, P2-S02 | 4 | NOT STARTED |
| P3-S02 | Metrics + rule baseline | TRAC-20 | Rafique | Ruhan | P0-S05 | 2.5 | NOT STARTED |
| P3-S03 | Reviewer UI | TRAC-21 | Ruhan | Rafique | P0-S03, P2-S05 | 4 | NOT STARTED |
| P3-S04 | Experiment runner + results page | TRAC-22 | Ruhan | Rafique | P2-S04 | 2.5 | NOT STARTED |
| P4-S01 | A3 experiments (E1, L0 vs G0, baseline) | TRAC-23 | Ruhan | Rafique | P2-S07, P3-S01, P3-S02, P3-S04 | 2 | NOT STARTED |
| P4-S02 | Failure analysis + results slides | TRAC-23 | Rafique | Ruhan | P4-S01 | 2 | NOT STARTED |
| P4-S03 | Demo script + submission pack | TRAC-23 | Ruhan | Rafique | P0-S04, P2-S06, P3-S03, P4-S02 | 1.5 | NOT STARTED |
| P5-S01 | Deeper graph + new fault families | TRAC-24 | Rafique | Ruhan | P4-S03 | 3 | NOT STARTED |
| P5-S02 | Statistics | TRAC-25 | Rafique | Ruhan | P4-S03 | 2 | NOT STARTED |
| P5-S03 | Full 2×2 × 3 runs | TRAC-28 | Ruhan | Rafique | P4-S03 | 3 | NOT STARTED |
| P5-S04 | Model sensitivity | TRAC-29 | Ruhan | Rafique | P5-S03 (G1 runs) | 2 | NOT STARTED |
| P5-S05 | BugsInPy subset (optional) | TRAC-27 | Rafique | Ruhan | P4-S03 | 2.5 | NOT STARTED |
| P6-S01 | Security hardening | TRAC-26 | Rafique | Ruhan | P4-S03 | 2.5 | NOT STARTED |
| P6-S02 | CI, images, public deployment | TRAC-30 | Ruhan | Rafique | P4-S03 | 3 | NOT STARTED |
| P6-S03 | UI polish + audit view | TRAC-31 | Ruhan | Rafique | P4-S03, P5-S02 | 2.5 | NOT STARTED |
| P6-S04 | Paper, docs, investor pitch | TRAC-32 | Rafique (+Ruhan) | Both | P5-S02, P5-S03 | 5 | NOT STARTED |

## Phases
| Phase | README | Goal | Exit milestone |
|---|---|---|---|
| 0 | [Foundation](phase-0-foundation/README.md) | Repo, scaffolds, contracts, approved scope | **M0:** `task dev` + `task web` run; contracts merged; supervisor reply saved |
| 1 | [Core components](phase-1-core-components/README.md) | Lab, sandbox, seed cases, incidents API, gateway, agent | **M1 (Sync 1):** agent produces records on 4 real cases |
| 2 | [Evidence-to-repair](phase-2-evidence-to-repair/README.md) | Real evidence, graph, retrieval, repair, report, GitHub | **M2 (Sync 2):** full pipeline end to end on 4 cases |
| 3 | [Dataset, evaluation, UI](phase-3-dataset-evaluation-ui/README.md) | 144 frozen cases, metrics, UI, runner | **M3:** frozen hash; UI clickable; runner works on dev |
| 4 | [A3 delivery](phase-4-a3-delivery/README.md) | Experiments, analysis, demo pack | **M4:** Assignment 3 demo ready |
| 5 | [Research completion](phase-5-research-completion/README.md) | Full 2×2, stats, model comparison | **M5:** all cells × 3 replicates with CIs |
| 6 | [Productization and paper](phase-6-productization-paper/README.md) | Security, CI, deployment, polish, paper | **M6:** Assignment 4 submission |

## Parallel lanes
```
Phase 0  R: S01 → S02 ──► S05(pair), S06-A      U: S03, S04 ─────► S05(pair), S06-B
Phase 1  R: S01 → S02 → S03 ─┐                 U: S04 → S05 → S06 ─┐
                              └──────── S07 Sync 1 (U) ◄────────────┘
Phase 2  R: S01, S02 → S03 ──┐                 U: S04 → S05, S06 ──┐
                              └──────── S07 Sync 2 (R) ◄────────────┘
Phase 3  R: S01, S02                           U: S03, S04
Phase 4  U: S01 → R: S02 → U: S03
Phase 5  R: S01, S02, S05                      U: S03, S04
Phase 6  R: S01, S04(lead)                     U: S02, S03, S04(support)
```
Notes: P1-S05 can start right after P0-S02 (doesn't need contracts). P3-S02 can start any time after P0-S05 (built on sample records), so Rafique can pull it forward if blocked.

## Critical path
`P0-S02 → P0-S05 → P1-S02 → P1-S03` (needs P1-S01) `→ P2-S01/P2-S02 → P2-S03 → P2-S07 → P3-S01 → P4-S01 → P4-S02 → P4-S03`

About 25 person-days along Rafique's lane. **Track A is the critical path for Assignment 3.** Ruhan's lane has slack in Phase 2; use it to pull P3-S03 forward.

## Blocking dependencies and integration points
| Point | What must be stable | Who waits |
|---|---|---|
| P0-S05 contracts | Field names, enums, samples | Everyone after Phase 0 |
| P1-S02 sandbox API | `run_tests(TestRunRequest) -> TestRunResult` | P1-S03, P2-S04 |
| P1-S07 Sync 1 | `CaseManifest` from real cases | P2-S04 testing on real cases |
| P2-S07 Sync 2 | `EvidenceBundle`, `ContextBundle` from real code | P3-S04 (real runs), P4-S01 |
| P3-S01 freeze | `test.sha256` | P4-S01 test-split runs; all tuning after it uses dev only |
| P3-S02 metrics | Report JSON format | P3-S04 results page |

## Scheduling bottlenecks
- **Dataset volume (P3-S01):** 144 validated cases + 30 dev is the largest single task. Mitigation: template parameterization from P1-S03; start variants during Phase 2 if graph work stalls.
- **Mistral free-tier throughput:** L0 vs G0 on ≥50 cases ≈ 100 runs × several calls each. Start P4-S01 runs as soon as the freeze lands; rely on the cache.
- **Supervisor approval (P0-S04):** external wait; send early.
- **Ruhan's access:** until he is a GitHub collaborator he cannot push; merges no longer need his approval.

## Milestone acceptance
- **M0:** P0-S02 and P0-S03 health checks pass on both laptops; P0-S05 samples validate; P0-S06 limits report written; revised proposal sent.
- **M1:** `task agent:run` on 4 seed cases produces schema-valid records; `task dataset:validate` green.
- **M2:** one command runs 4 cases end to end with real evidence/context; config + code reach `TEST_VERIFIED_IN_LAB` or have documented failures; decoy and abstain behave correctly.
- **M3:** frozen manifest with ≥60/60/12/12 test + ≥30 dev, ≥50% distance ≥1; UI flow clickable; dev-split run resumable.
- **M4:** E1 on all cases, L0 vs G0 on ≥50, rule baseline, ≥10 failure analyses, latency/cost, clean-clone dry run.
- **M5:** 4 conditions × 3 replicates complete; CIs, McNemar, interaction computed; model comparison table.
- **M6:** security suite and CI green; public link; paper and pitch done.
