# Implementation roadmap

From the current state (repo + docs + board, no code) to the final Assignment 4 deliverable. Owners match [TEAM_WORK_DISTRIBUTION.md](TEAM_WORK_DISTRIBUTION.md). Status column synced 2026-11-25 for Ruhan's 20 primary steps using the five-fact model (implemented / tested / integrated / reviewed / approved; see `RUHAN_TASK_TRACKER.md`, authoritative). Nothing is reviewed or approved, so nothing is COMPLETE & VERIFIED. Rafique's rows are copied from `TEAM_WORK_DISTRIBUTION.md` and not independently verified here; rows still reading NOT STARTED are unchanged.

## Task-to-card map
| ID | Task | Card | Owner | Reviewer | Depends on | Effort (d) | Status |
|---|---|---|---|---|---|---|---|
| P0-S01 | Repository and collaboration setup | — | Rafique | Ruhan | — | 0.5 | IN PROGRESS |
| P0-S02 | Backend scaffold | TRAC-1 | Rafique | Ruhan | P0-S01 | 1 | COMPLETED |
| P0-S03 | Frontend scaffold | TRAC-2 | Ruhan | Rafique | P0-S01 | 1 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| P0-S04 | Proposal update and supervisor approval | TRAC-3 | Ruhan | Rafique | — | 1 | PARTIALLY COMPLETE (no written approval of revised scope) |
| P0-S05 | Shared contracts + samples | TRAC-4 | Rafique (+Ruhan) | Both | P0-S02 | 1 | COMPLETED |
| P0-S06 | Feasibility prototype (retrieval spike + model probe) | — | Rafique (A) + Ruhan (B) | optional | P0-S02 | 2 + 2 | A DONE; B (Ruhan, supporting) IMPLEMENTED, PARTLY RUN |
| P1-S01 | Lab fixtures | TRAC-5 | Rafique | Ruhan | P0-S02 | 2.5 | IMPLEMENTED (per TWD; not reviewed by Rafique) |
| P1-S02 | Sandbox test runner | TRAC-6 | Rafique | Ruhan | P0-S05 | 2 | IMPLEMENTED (per TWD; not reviewed by Rafique) |
| P1-S03 | Fault generator + 4 seed cases | TRAC-7 | Rafique | Ruhan | P1-S01, P1-S02 | 3 | COMPLETED |
| P1-S04 | Incidents API + DB | TRAC-8 | Ruhan | Rafique | P0-S05 | 2 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| P1-S05 | Model gateway + cache + ADR 0001 | TRAC-9 | Ruhan | Rafique | P0-S02 | 2 | PARTIALLY COMPLETE (ADR 0001 PROPOSED) |
| P1-S06 | Pipeline agent | TRAC-10 | Ruhan | Rafique | P1-S04, P1-S05 | 3 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| P1-S07 | Sync 1: agent on real seed cases | TRAC-11 | Ruhan (+Rafique) | Rafique | P1-S03, P1-S06 | 0.5 | IMPLEMENTED, TESTED (test_sync1, 7); NOT REVIEWED/APPROVED |
| P2-S01 | Evidence collector | TRAC-12 | Rafique | Ruhan | P0-S05, P1-S01 | 2.5 | IMPLEMENTED (per TWD) |
| P2-S02 | Code graph | TRAC-13 | Rafique | Ruhan | P1-S01 | 3 | IMPLEMENTED (per TWD; not reviewed by Rafique) |
| P2-S03 | Retrieval L and G + E1 | TRAC-14 | Rafique | Ruhan | P2-S01, P2-S02 | 3 | IMPLEMENTED (per TWD; not reviewed by Rafique) |
| P2-S04 | Repair loop | TRAC-15 | Ruhan | Rafique | P1-S02, P1-S06 | 3.5 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| P2-S05 | Report and review | TRAC-16 | Ruhan | Rafique | P1-S04, P2-S04 | 1.5 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| P2-S06 | GitHub intake | TRAC-17 | Ruhan | Rafique | P1-S04 | 1.5 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| P2-S07 | Sync 2: full pipeline | TRAC-18 | Rafique (+Ruhan) | Ruhan | P2-S03, P2-S04, P2-S05 | 1 | NOT STARTED |
| P3-S01 | Dataset scale-up and freeze | TRAC-19 | Rafique | Ruhan | P1-S03, P2-S02 | 4 | COMPLETED (23 Nov) |
| P3-S02 | Metrics + rule baseline | TRAC-20 | Rafique | Ruhan | P0-S05 | 2.5 | IMPLEMENTED (per TWD) |
| P3-S03 | Reviewer UI | TRAC-21 | Ruhan | Rafique | P0-S03, P2-S05 | 4 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| P3-S04 | Experiment runner + results page | TRAC-22 | Ruhan | Rafique | P2-S04 | 2.5 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| P4-S01 | A3 experiments (E1, L0 vs G0, baseline) | TRAC-23 | Ruhan | Rafique | P2-S07, P3-S01, P3-S02, P3-S04 | 2 | PARTIALLY COMPLETE (reduced evaluation only; owner decision open) |
| P4-S02 | Failure analysis + results slides | TRAC-23 | Rafique | Ruhan | P4-S01 | 2 | NOT STARTED |
| P4-S03 | Demo script + submission pack | TRAC-23 | Ruhan | Rafique | P0-S04, P2-S06, P3-S03, P4-S02 | 1.5 | PARTIALLY COMPLETE (no dry run) |
| P5-S01 | Deeper graph + new fault families | TRAC-24 | Rafique | Ruhan | P4-S03 | 3 | NOT STARTED |
| P5-S02 | Statistics | TRAC-25 | Rafique | Ruhan | P4-S03 | 2 | NOT STARTED |
| P5-S03 | Full 2×2 × 3 runs | TRAC-28 | Ruhan | Rafique | P4-S03 | 3 | PARTIALLY COMPLETE (reduced evaluation) |
| P5-S04 | Model sensitivity | TRAC-29 | Ruhan | Rafique | P5-S03 (G1 runs) | 2 | PARTIALLY COMPLETE (setup + monitor; no comparison) |
| P5-S05 | BugsInPy subset (optional) | TRAC-27 | Rafique | Ruhan | P4-S03 | 2.5 | NOT STARTED |
| P5-S06 | Retrieval benchmark + baselines RET-L / RET-G (dev, 0 tokens) | — | Rafique | Ruhan | P3-S01 (done), review of P2-S02/S03 | 1.5 | NOT STARTED |
| P5-S07 | Incremental chunk manifest, embedding cache, index verifier | — | Rafique | Ruhan | P5-S06 (data model parallel) | 2 | NOT STARTED |
| P5-S08 | RET-E + fusion arms, ADR 0003 decision gate | — | Rafique | Ruhan | P5-S06, P5-S07 | 2 | NOT STARTED |
| P5-S09 | Optional reranking | — | Rafique | Ruhan | P5-S08 go | 1 | NOT STARTED |
| P5-S10 | RC2 candidate: pipeline robustness fixes (needs owner approval) | — | Ruhan | Rafique | none (approval to start) | 2 | IMPLEMENTED opt-in, TESTED (17); NOT VALIDATED/APPROVED |
| P5-S11 | Conditional end-to-end hybrid experiment | — | Ruhan (+Rafique) | Rafique | P5-S08 go (+P5-S10) | 2 | NOT STARTED |
| P5-S12 | Traversal overlay + root-cause ranker (MVP, proposed 2026-11-25) | — | Rafique | Ruhan | P5-S06 | 3 | NOT STARTED |
| P5-S13 | Config value-flow analysis (Tier 2, proposed) | — | Rafique | Ruhan | P5-S12 (+MVP gain) | 3 | NOT STARTED |
| P5-S14 | Runtime evidence fusion (Tier 2, proposed) | — | Rafique | Ruhan | P5-S12 (+MVP gain) | 1.5 | NOT STARTED |
| P5-S15 | Change-impact report + visible-test selection (MVP, proposed) | — | Rafique | Ruhan | P5-S06 (S12 optional) | 2.5 | NOT STARTED |
| P5-S16 | Root-cause and impact evaluation suite (MVP reduced 1.5 d; full 3 d) | — | Rafique (Ruhan verifies labels) | Ruhan | P5-S06; S12/S15 incrementally | 3 | NOT STARTED |
| P5-S17 | Regression-aware repair validation (conditional, RC2; owner approval) | — | Ruhan (+Rafique) | Rafique | P5-S10, P5-S15, P5-S16 benefit | 3 | NOT STARTED |
| P6-S01 | Security hardening | TRAC-26 | Rafique | Ruhan | P4-S03 | 2.5 | NOT STARTED |
| P6-S02 | CI, images, public deployment | TRAC-30 | Ruhan | Rafique | P4-S03 | 3 | PARTIALLY COMPLETE (no GitHub run, no host) |
| P6-S03 | UI polish + audit view | TRAC-31 | Ruhan | Rafique | P4-S03, P5-S02 | 2.5 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
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
Phase 5  R: S01, S02, S05 | S06 -> S07 -> S08 -> S09?   U: S03, S04 | S10 (approval), S11 (if S08 go)
         + proposed 25 Nov: MVP R: S06 -> S12 -> S15 -> S16(reduced) | Tier 2 R: S13, S14 (after MVP gain) | conditional U: S17 (needs S10, S15/S16 benefit, owner approval)
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
- **Mistral free-tier throughput (superseded: the experiment model is AxForge glm-5.3-flash; Key-1 ledger 152,664 tokens left on 2026-11-25):** L0 vs G0 on ≥50 cases ≈ 100 runs × several calls each. Start P4-S01 runs as soon as the freeze lands; rely on the cache.
- **Supervisor approval (P0-S04):** external wait; send early.
- **Ruhan's access:** until he is a GitHub collaborator he cannot push; merges no longer need his approval.

## Milestone acceptance
- **M0:** P0-S02 and P0-S03 health checks pass on both laptops; P0-S05 samples validate; P0-S06 limits report written; revised proposal sent.
- **M1:** `task agent:run` on 4 seed cases produces schema-valid records; `task dataset:validate` green.
- **M2:** one command runs 4 cases end to end with real evidence/context; config + code reach `TEST_VERIFIED_IN_LAB` or have documented failures; decoy and abstain behave correctly.
- **M3:** frozen manifest with ≥60/60/12/12 test + ≥30 dev, ≥50% distance ≥1; UI flow clickable; dev-split run resumable.
- **M4:** E1 on all cases, L0 vs G0 on ≥50, rule baseline, ≥10 failure analyses, latency/cost, clean-clone dry run.
- **M5:** 4 conditions × 3 replicates complete; CIs, McNemar, interaction computed; model comparison table.
- **M5b (follow-up study, conditional, added 2026-11-24):** P5-S06 baselines on dev saved with CIs; P5-S07 verifier green; P5-S08 preregistered results and ADR 0003 (PROPOSED) with go/no-go; RC1 fingerprint `ee3d8d87...` unchanged; 0 tokens for S06 to S09. P5-S09, P5-S10, P5-S11 only as approved.
- **M5c (root-cause and impact study, PROPOSED 2026-11-25, pending owner approval Q18):** MVP = P5-S12 overlay and ranker, P5-S15 impact report, P5-S16 reduced set (4 families x 3 cases) with thresholds preregistered before any run and labels verified by the second person; RC1 fingerprint unchanged; 0 tokens. Tier 2 (P5-S13 value flow, P5-S14 runtime evidence, full S16 8 x 5) only if the MVP shows a measurable gain. Conditional: P5-S17 (RC2 only) needs owner approval, P5-S10 and S15/S16 benefit. Ordering: S06 -> S12 -> S15 (S15 may start right after S06) -> S16 reduced -> decision -> S13/S14 -> full S16 -> S17. Capacity is an owner/Rafique decision; effort figures are ASSUMPTION.
- **M6:** security suite and CI green; public link; paper and pitch done.
