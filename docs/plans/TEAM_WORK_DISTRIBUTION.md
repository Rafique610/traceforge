# Team work distribution

Members come from the project docs: **Muhammad Rafique** and **Muhammad Ruhan Kamran**. No one else is on the team. Every task has one primary owner; review by the other member is optional.

The split follows one rule: **each person owns whole folders**, and the two halves exchange data only through the five shared contracts (P0-S05). That lets both work at the same time with almost no waiting.

## 0. Progress at a glance
**Updated before every commit by whoever commits** (rule in `docs/invariants/processes.md`). Last updated: 22 Nov 2026, with the validated and frozen dataset.

"Done" = approved by the step's owner. "Implemented" = code on `main` that its owner has not yet approved (much of Track A was written by Ruhan's Claude-assisted session; see section 7).

| | Muhammad Rafique (Track A) | Muhammad Ruhan Kamran (Track B) |
|---|---|---|
| **Steps done** | 2 / 19 (P0-S02, P0-S05); P0-S06 Part A done | 0 / 20 approved; 5 implemented (P0-S03, P1-S04, P1-S05 partial, P1-S06, P2-S04 core) |
| **Working on** | Dataset FROZEN: test 151 (60/67/12/12), dev 33, 184/184 validated; awaiting owner approval | Review own steps; P0-S04 proposal; pick the experiment model (ADR 0001) |
| **Next up** | Dataset to ≥144 test + ≥30 dev and freeze; re-run lab + sandbox live; evidence/graph/retrieval gaps | P1-S07 Sync 1 once more cases exist; P2-S05, P2-S06 |
| **Waiting on the other** | Ruhan: model decision for experiments | — (frozen dataset now on `main`: unblocks P1-S07, P3-S04, P4-S01, P5-S03/S04) |

| Phase | Rafique | Status | Ruhan | Status |
|---|---|---|---|---|
| 0 | P0-S01 Repo setup | IN PROGRESS (Ruhan's clone left) | P0-S03 Frontend scaffold | IMPLEMENTED, NEEDS REVIEW |
| 0 | P0-S02 Backend scaffold | COMPLETED | P0-S04 Proposal update | DRAFTED; blocked on PDF + supervisor |
| 0 | P0-S05 Contracts | COMPLETED (change approved, D35) | P0-S05 Contracts (confirm) | COMPLETED |
| 0 | P0-S06 Part A retrieval spike | DONE | P0-S06 Part B model probe | IMPLEMENTED, PARTLY RUN (no Devstral run) |
| 1 | P1-S01 Lab fixtures | IMPLEMENTED; extended by Rafique (stock, coupons, shipping, quote) | P1-S04 Incidents API | IMPLEMENTED, NEEDS REVIEW |
| 1 | P1-S02 Sandbox | IMPLEMENTED; self-test passes on Rafique's laptop | P1-S05 Model gateway | IMPLEMENTED, PARTLY VERIFIED |
| 1 | P1-S03 Seed cases | NEEDS REVIEW: 184 cases validated | P1-S06 Pipeline agent | IMPLEMENTED (fake gateway tests) |
| 1 | — | — | P1-S07 Sync 1 | NOT STARTED (needs cases) |
| 2 | P2-S01 Evidence collector | IMPLEMENTED; 66 tests pass with pinned proxy | P2-S04 Repair loop | CORE IMPLEMENTED |
| 2 | P2-S02 Code graph | IMPLEMENTED, not reviewed | P2-S05 Report + review | NOT STARTED |
| 2 | P2-S03 Retrieval L/G | IMPLEMENTED; E1 not meaningful yet | P2-S06 GitHub intake | NOT STARTED |
| 2 | P2-S07 Sync 2 | NOT STARTED | — | — |
| 3 | P3-S01 Dataset freeze | NEEDS REVIEW: test split frozen (sha256 881f2887…) | P3-S03 Reviewer UI | NOT STARTED |
| 3 | P3-S02 Metrics + baseline | IMPLEMENTED; needs real runs | P3-S04 Runner + results page | NOT STARTED |
| 4 | 0 / 1 done | NOT STARTED | 0 / 2 done | NOT STARTED |
| 5 | 0 / 3 done | NOT STARTED | 0 / 2 done | NOT STARTED |
| 6 | 0 / 2 done | NOT STARTED | 0 / 3 done | NOT STARTED |

When a phase starts, replace its count row with one row per step, as Phases 0–3 show.

## 1. Team overview
| Member | Primary role | Assigned modules | Main responsibilities |
|---|---|---|---|
| Muhammad Rafique | Track A: evidence-side engineer; repo owner | `lab/`, `datasets/`, `backend/traceforge/{health,sandbox,evidence,codeintel,retrieval}/`, `evaluation/{metrics,baselines,analysis}` | Victim lab, fault dataset, sandbox runner, evidence collection, code graph, retrieval (the RAG part and the research contribution), metrics and statistics, security hardening, paper lead |
| Muhammad Ruhan Kamran | Track B: agent-side engineer | `backend/traceforge/{incidents,agent,repair,reports,reviews,github}/`, `evaluation/runner.py`, `evaluation/conditions/`, `frontend/` | Incident API and state machine, LLM gateway, pipeline agent (the agentic tool-calling part), repair loop, report/review, GitHub integration, reviewer UI, experiment runner, CI/deployment, proposal update |

Shared (PR approved by both): `backend/traceforge/contracts/`, `main.py`, `config.py`, `database.py`, `pyproject.toml`, `Taskfile.yml`, root `compose.yaml`, `docs/`, `README.md`.

## 2. Individual responsibilities

### 2.1 Muhammad Rafique
1. **Role:** Track A, evidence side. Repository owner (settings, collaborators, branch protection).
2. **Ownership:** everything that turns a failure into evidence, ranked context and a trustworthy test result; everything that turns run records into metrics.
3. **Phases:** 0, 1, 2, 3, 4, 5, 6.
4. **Steps (primary):** P0-S01, P0-S02, P0-S05, P1-S01, P1-S02, P1-S03, P2-S01, P2-S02, P2-S03, P2-S07, P3-S01, P3-S02, P4-S02, P5-S01, P5-S02, P5-S05, P6-S01, P6-S04.
5. **Technical responsibilities:** FastAPI app core; Docker Compose lab design; Docker SDK and container isolation; pytest-based validators; fault mutation templates; Python `ast`; networkx graph; BM25 ranking; IR metrics (Recall@K, MRR, nDCG); bootstrap and McNemar statistics; security tests.
6. **Deliverables:** running lab with contracts; sandbox runner; ≥144 validated, frozen cases + ≥30 dev; evidence collector; code graph; L/G retrieval and E1 results; metrics + rule baseline; failure analysis; A4 statistics; security suite; paper method/data/evaluation sections.
7. **Knowledge needed:** Docker/Compose networking and resource limits, Python AST, information retrieval, basic statistics.
8. **Depends on Ruhan for:** `AgentRunRecord`s from the runner (P3-S04) to compute repair/diagnosis metrics; agent CLI for Sync 2 (P2-S07).
9. **Reviews:** all Track B PRs (P0-S03, P1-S04, P1-S05, P1-S06, P2-S04, P2-S05, P2-S06, P3-S03, P3-S04, P4-S01, P4-S03, P5-S03, P5-S04, P6-S02, P6-S03) and the proposal (P0-S04).

### 2.2 Muhammad Ruhan Kamran
1. **Role:** Track B, agent side.
2. **Ownership:** everything from context to diagnosis, patch, verified outcome, report, review and the user-facing app.
3. **Phases:** 0, 1, 2, 3, 4, 5, 6.
4. **Steps (primary):** P0-S03, P0-S04, P1-S04, P1-S05, P1-S06, P1-S07, P2-S04, P2-S05, P2-S06, P3-S03, P3-S04, P4-S01, P4-S03, P5-S03, P5-S04, P6-S02, P6-S03.
5. **Technical responsibilities:** SQLAlchemy models, Alembic, state machine; OpenAI-compatible client, tool schemas, caching, rate limits; prompt design; unified-diff parsing and git worktrees; GitHub REST; React/TypeScript UI; GitHub Actions; deployment.
6. **Deliverables:** incident API; gateway + ADR 0001; pipeline agent; repair loop with F0/F1 and no-leak test; report/review; GitHub intake; reviewer UI; experiment runner + results page; A3 experiment runs; demo and submission pack; A4 factorial runs and model comparison; CI and public deployment; paper system/agent sections and investor pitch; updated proposal.
7. **Knowledge needed:** FastAPI/SQLAlchemy, LLM tool calling, prompt engineering, git internals, React.
8. **Depends on Rafique for:** contracts (P0-S05, shared); sandbox runner (P1-S02) for P2-S04 (uses a fake runner until then); real cases (P1-S03) for Sync 1; real evidence/context (P2-S01, P2-S03) for Sync 2; frozen manifest (P3-S01) for test-split runs; metrics (P3-S02) for the results page.
9. **Reviews:** all Track A PRs (P0-S02, P1-S01…S03, P2-S01…S03, P3-S01, P3-S02, P4-S02, P5-S01, P5-S02, P5-S05, P6-S01) and the label peer-check in P3-S01.

## 3. Individual task checklists

### Muhammad Rafique
- [ ] [P0-S01](phase-0-foundation/step-01-repository-and-collaboration-setup.md) Repository and collaboration setup
- [x] [P0-S02](phase-0-foundation/step-02-backend-scaffold.md) Backend scaffold (TRAC-1)
- [x] [P0-S05](phase-0-foundation/step-05-shared-contracts.md) Shared contracts, primary owner (TRAC-4)
- [ ] [P0-S06](phase-0-foundation/step-06-feasibility-prototype.md) Feasibility prototype, Part A: retrieval spike
- [ ] [P1-S01](phase-1-core-components/step-01-lab-fixtures.md) Lab fixtures (TRAC-5)
- [ ] [P1-S02](phase-1-core-components/step-02-sandbox-test-runner.md) Sandbox test runner (TRAC-6)
- [ ] [P1-S03](phase-1-core-components/step-03-fault-generator-and-seed-cases.md) Fault generator + 4 seed cases (TRAC-7)
- [ ] [P2-S01](phase-2-evidence-to-repair/step-01-evidence-collector.md) Evidence collector (TRAC-12)
- [ ] [P2-S02](phase-2-evidence-to-repair/step-02-code-graph.md) Code graph (TRAC-13)
- [ ] [P2-S03](phase-2-evidence-to-repair/step-03-retrieval-l-and-g.md) Retrieval L and G + E1 (TRAC-14)
- [ ] [P2-S07](phase-2-evidence-to-repair/step-07-sync-2-full-pipeline.md) Sync 2, primary owner (TRAC-18)
- [ ] [P3-S01](phase-3-dataset-evaluation-ui/step-01-dataset-scale-up-and-freeze.md) Dataset scale-up and freeze (TRAC-19)
- [ ] [P3-S02](phase-3-dataset-evaluation-ui/step-02-evaluation-metrics-and-baseline.md) Metrics + rule baseline (TRAC-20)
- [ ] [P4-S02](phase-4-a3-delivery/step-02-failure-analysis-and-results.md) Failure analysis and results (TRAC-23)
- [ ] [P5-S01](phase-5-research-completion/step-01-deeper-graph.md) Deeper graph (TRAC-24)
- [ ] [P5-S02](phase-5-research-completion/step-02-statistics.md) Statistics (TRAC-25)
- [ ] [P5-S05](phase-5-research-completion/step-05-bugsinpy-subset.md) BugsInPy subset, optional (TRAC-27)
- [ ] [P6-S01](phase-6-productization-paper/step-01-security-hardening.md) Security hardening (TRAC-26)
- [ ] [P6-S04](phase-6-productization-paper/step-04-paper-and-pitch.md) Paper, primary owner (TRAC-32)
- [ ] Review every Track B PR within one working day.

### Muhammad Ruhan Kamran
- [ ] [P0-S03](phase-0-foundation/step-03-frontend-scaffold.md) Frontend scaffold (TRAC-2)
- [ ] [P0-S04](phase-0-foundation/step-04-proposal-update-and-approval.md) Proposal update and approval (TRAC-3)
- [ ] [P0-S05](phase-0-foundation/step-05-shared-contracts.md) Shared contracts, supporting member: confirm the fields and samples
- [ ] [P0-S06](phase-0-foundation/step-06-feasibility-prototype.md) Feasibility prototype, Part B: model probe
- [ ] [P1-S04](phase-1-core-components/step-04-incidents-api-and-database.md) Incidents API + DB (TRAC-8)
- [ ] [P1-S05](phase-1-core-components/step-05-model-gateway.md) Model gateway + ADR 0001 (TRAC-9)
- [ ] [P1-S06](phase-1-core-components/step-06-pipeline-agent.md) Pipeline agent (TRAC-10)
- [ ] [P1-S07](phase-1-core-components/step-07-sync-1-agent-on-seed-cases.md) Sync 1, primary owner (TRAC-11)
- [ ] [P2-S04](phase-2-evidence-to-repair/step-04-repair-loop.md) Repair loop (TRAC-15)
- [ ] [P2-S05](phase-2-evidence-to-repair/step-05-report-and-review.md) Report and review (TRAC-16)
- [ ] [P2-S06](phase-2-evidence-to-repair/step-06-github-intake.md) GitHub intake (TRAC-17)
- [ ] [P3-S03](phase-3-dataset-evaluation-ui/step-03-reviewer-ui.md) Reviewer UI (TRAC-21)
- [ ] [P3-S04](phase-3-dataset-evaluation-ui/step-04-experiment-runner-and-results-page.md) Experiment runner + results page (TRAC-22)
- [ ] [P4-S01](phase-4-a3-delivery/step-01-a3-experiments.md) A3 experiments (TRAC-23)
- [ ] [P4-S03](phase-4-a3-delivery/step-03-demo-and-submission-pack.md) Demo and submission pack (TRAC-23)
- [ ] [P5-S03](phase-5-research-completion/step-03-full-factorial-runs.md) Full 2×2 runs (TRAC-28)
- [ ] [P5-S04](phase-5-research-completion/step-04-model-sensitivity.md) Model sensitivity (TRAC-29)
- [ ] [P6-S02](phase-6-productization-paper/step-02-ci-and-deployment.md) CI and deployment (TRAC-30)
- [ ] [P6-S03](phase-6-productization-paper/step-03-ui-polish-and-audit-view.md) UI polish and audit view (TRAC-31)
- [ ] [P6-S04](phase-6-productization-paper/step-04-paper-and-pitch.md) Paper system/agent sections + investor pitch, supporting member
- [ ] Review every Track A PR within one working day.

## 4. Workload balance
Effort is in **person-days**, a planning estimate from task size, not a measurement. Revisit after Phase 1 using real durations.

| Phase | Rafique | Ruhan |
|---|---|---|
| 0 | P0-S01 0.5 · P0-S02 1 · P0-S05 1 · P0-S06-A 2 = **4.5** | P0-S03 1 · P0-S04 1 · P0-S05 (pair) 0.5 · P0-S06-B 2 = **4.5** |
| 1 | P1-S01 2.5 · P1-S02 2 · P1-S03 3 = **7.5** | P1-S04 2 · P1-S05 2 · P1-S06 3 · P1-S07 0.5 = **7.5** |
| 2 | P2-S01 2.5 · P2-S02 3 · P2-S03 3 · P2-S07 1 = **9.5** | P2-S04 3.5 · P2-S05 1.5 · P2-S06 1.5 = **6.5** |
| 3 | P3-S01 4 · P3-S02 2.5 = **6.5** | P3-S03 4 · P3-S04 2.5 = **6.5** |
| 4 | P4-S02 2 = **2** | P4-S01 2 · P4-S03 1.5 = **3.5** |
| 5 | P5-S01 3 · P5-S02 2 · P5-S05 2.5 = **7.5** | P5-S03 3 · P5-S04 2 = **5** |
| 6 | P6-S01 2.5 · P6-S04 2.5 (half of paper) = **5** | P6-S02 3 · P6-S03 2.5 · P6-S04 2.5 = **8** |
| **Total** | **42.5** | **41.5** |

**Analysis**
- Totals are within 3% of each other. By phase they differ, by design: Rafique carries more in Phase 2 (graph + retrieval is the research core), Ruhan carries more in Phase 6 (CI, deployment, UI polish).
- **Rafique's Phase 2 is the critical path** (P2-S01 → P2-S03 blocks Sync 2). If it slips, Ruhan picks up P2-S07's wiring work (he owns the consuming side anyway) and Rafique keeps P2-S03.
- **Ruhan's Phase 2 has ~3 days of slack.** Use it to start P3-S03 (UI) early against contract samples, which reduces Phase 3 risk.
- P5-S05 (BugsInPy) is optional. If Rafique is overloaded in A4, drop it first.
- Highest technical difficulty: P2-S02 (graph), P2-S04 (repair loop), P1-S06 (agent), P3-S01 (dataset volume). They are split two per person.

## 5. Shared responsibilities
| Task | Primary | Supporting | Reviewer | Coordination | Handoff |
|---|---|---|---|---|---|
| P0-S05 Contracts | Rafique | Ruhan | Both approve | One pair session; any later change = its own PR approved by both | Samples in `contracts/samples/` both tracks build against |
| P1-S07 Sync 1 | Ruhan | Rafique | Rafique | Rafique on call for manifest questions | 4 real `AgentRunRecord`s; contract fixes merged |
| P2-S07 Sync 2 | Rafique | Ruhan | Ruhan | Joint session; Ruhan wires agent to real evidence/context | One command runs 4 cases end to end on both laptops |
| P3-S01 label peer check | Rafique | Ruhan (checks 10 random cases) | Ruhan | Comment on TRAC-19 | Frozen hash |
| P4-S01 / S02 / S03 | Ruhan / Rafique / Ruhan | the other | the other | Shared dry run | Submission pack |
| P6-S04 Paper | Rafique | Ruhan | Both | Section split listed in the step | Final PDF |

## 6. Ownership consistency
The owners above are the same in [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md), every phase README and every step document. The Synverk card titles name the same owner. Cards are **not assigned in Synverk yet** because Ruhan is not a project member; see [DECISIONS_AND_OPEN_QUESTIONS.md](DECISIONS_AND_OPEN_QUESTIONS.md#open-questions).


## 7. Implementation record (who actually implemented what; added 2026-11-21, uncommitted)
Ownership above is unchanged (it is the plan). On 2026-11-21 Ruhan authorised a Claude-assisted session to implement, for Ruhan, the Track A components his tasks depend on. Nothing of Rafique's existing work was overwritten. Details and evidence: `DEPENDENCY_MAP_RAFIQUE.md` section D.
| Step | Original owner | Implemented by | State |
|---|---|---|---|
| P1-S01 Lab fixtures | Rafique | Claude-assisted, for Ruhan | implemented, verified on real stack; realism fix in progress |
| P1-S02 Sandbox | Rafique | same | implemented, verified in real containers |
| P1-S03 Seed cases | Rafique | same | 4 dev cases validated in real sandbox |
| P2-S01 Evidence collector | Rafique | same | implemented, verified on real lab |
| P2-S02 Code graph | Rafique | same | implemented, tested |
| P2-S03 Retrieval | Rafique | same | implemented; E1 not meaningful yet |
| P3-S02 Metrics + baseline | Rafique | same | implemented; run on real records |
| P3-S01 Dataset freeze | Rafique | — | not done |
| Contract `AgentRunRecord` (B9, B13) | shared | Claude-assisted | additive change; **Rafique must review** |
All Ruhan-track steps: implemented by the Claude-assisted session for Ruhan; none is approved yet (only Ruhan approves). The checklist is `RUHAN_CHECKLIST.md`; the evidence audit is `RUHAN_AUDIT.md`.
