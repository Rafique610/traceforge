# Team work distribution

Members come from the project docs: **Muhammad Rafique** and **Muhammad Ruhan Kamran**. No one else is on the team. Every task has one primary owner; review by the other member is optional.

The split follows one rule: **each person owns whole folders**, and the two halves exchange data only through the five shared contracts (P0-S05). That lets both work at the same time with almost no waiting.

## 0. Progress at a glance
**Updated before every commit by whoever commits** (rule in `docs/invariants/processes.md`). Last updated: 25 Nov 2026 (final status sync, see below); the Rafique column was last updated 25 Nov 2026 with P5-S06 reviewed, reproduced and approved. Also 25 Nov 2026: BeatAPI calls in the gateway (P1-S05 area, Ruhan's module) are now streamed with a 2,048-token cap, which fixed the provider's 503 on long diagnoses; first live free-model run through the real Investigate path fixed shop_api-002 end to end (VERIFIED, REVIEW_PENDING, same patch as the known fix). One case only; the browser click path is not yet tested. On 24 Nov 2026 six Phase 5 tasks (P5-S06 to P5-S11, retrieval modernization study) were added at the owner's request; see section 7. On 25 Nov 2026 six more Phase 5 tasks (P5-S12 to P5-S17, root-cause and impact analysis study) were added as PROPOSED, pending owner approval (Q18).

"Done" = approved by the step's owner. "Implemented" = code on `main` that its owner has not yet approved (much of Track A was written by Ruhan's Claude-assisted session; see section 7).

**Status sync 2026-11-25 (Ruhan's column).** Each task carries five separate facts: IMPLEMENTED / TESTED / INTEGRATED / REVIEWED / APPROVED, plus one overall label (COMPLETE & VERIFIED, IMPLEMENTED NOT VERIFIED, PARTIALLY COMPLETE, NOT STARTED, BLOCKED). Nothing is REVIEWED (Rafique's review of Ruhan's code is outstanding) or APPROVED (no owner approval is recorded), so no Ruhan task is COMPLETE & VERIFIED and "0 of 20 approved" stays true. Per-task detail: `RUHAN_TASK_TRACKER.md` (authoritative) and `RUHAN_CHECKLIST.md`. Counts: Ruhan has exactly **20** primary steps (the list in section 2.2); P0-S05, P0-S06 Part B and P6-S04 are supporting only, plus the P5-S16 label verification. Earlier figures of 22 or 23 for Ruhan were wrong (they counted supporting items and double counted).

| | Muhammad Rafique (Track A) | Muhammad Ruhan Kamran (Track B) |
|---|---|---|
| **Steps done** | 5 / 28 (P0-S02, P0-S05, P1-S03, P3-S01, P5-S06); P0-S06 Part A done | 0 / 20 approved (none reviewed by Rafique); by label: 10 IMPLEMENTED, NOT VERIFIED; 10 PARTIALLY COMPLETE (incl. P5-S10, P5-S11, P5-S17); 0 COMPLETE & VERIFIED |
| **Working on** | Reviewing the P5 work built by Ruhan's session: P5-S06 approved (31 dev cases reproduced); P5-S07 next | Awaiting Rafique's review and owner approval; P0-S04 proposal approval evidence; ADR 0001 model decision (owner) |
| **Next up** | Review P1-S01/S02, P2-S01…S03; note the additive contract schema change (`agent_run_record`, `evidence_bundle`); P3-S02 metrics on real runs | Owner decisions: AxForge investigation for the real patch path (about 30k tokens), RC2 blind validation, ADR 0001; Q19 is DECIDED (reduced RC1 evaluation adopted, shortfall disclosed) |
| **Waiting on the other** | Ruhan: model decision for experiments | — (frozen dataset now on `main`: unblocks P1-S07, P3-S04, P4-S01, P5-S03/S04) |

| Phase | Rafique | Status | Ruhan | Status |
|---|---|---|---|---|
| 0 | P0-S01 Repo setup | IN PROGRESS (Ruhan's clone left) | P0-S03 Frontend scaffold | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| 0 | P0-S02 Backend scaffold | COMPLETED | P0-S04 Proposal update | PARTIALLY COMPLETE (revised PDF dated 23 Nov exists; the 18 Nov supervisor email is conditional written permission to proceed; written confirmation of the revised scope is not on disk) |
| 0 | P0-S05 Contracts | COMPLETED (change approved, D35) | P0-S05 Contracts (confirm) | supporting; additive change awaits Rafique review |
| 0 | P0-S06 Part A retrieval spike | DONE | P0-S06 Part B model probe | supporting; IMPLEMENTED, PARTLY RUN (no Devstral run) |
| 1 | P1-S01 Lab fixtures | IMPLEMENTED; extended by Rafique (stock, coupons, shipping, quote) | P1-S04 Incidents API | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| 1 | P1-S02 Sandbox | IMPLEMENTED; self-test passes on Rafique's laptop | P1-S05 Model gateway | PARTIALLY COMPLETE (tested; ADR 0001 still PROPOSED) |
| 1 | P1-S03 Seed cases | COMPLETED: 184 cases validated | P1-S06 Pipeline agent | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| 1 | — | — | P1-S07 Sync 1 | IMPLEMENTED, TESTED (`tests/integration/test_sync1.py`, 7 tests, fake gateway), partially integrated (no both-members run recorded); NOT REVIEWED/APPROVED |
| 2 | P2-S01 Evidence collector | IMPLEMENTED; 66 tests pass with pinned proxy | P2-S04 Repair loop | IMPLEMENTED, TESTED (64 repair tests); NOT REVIEWED/APPROVED |
| 2 | P2-S02 Code graph | IMPLEMENTED, not reviewed | P2-S05 Report + review | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| 2 | P2-S03 Retrieval L/G | IMPLEMENTED; E1 not meaningful yet | P2-S06 GitHub intake | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| 2 | P2-S07 Sync 2 | NOT STARTED | — | — |
| 3 | P3-S01 Dataset freeze | COMPLETED: test split frozen (sha256 881f2887…) | P3-S03 Reviewer UI | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| 3 | P3-S02 Metrics + baseline | IMPLEMENTED; needs real runs | P3-S04 Runner + results page | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| 4 | 0 / 1 done | NOT STARTED | 0 / 2 done | P4-S01 PARTIALLY COMPLETE (Q19 DECIDED: reduced RC1 evaluation adopted as the A3 final evaluation for diagnosis/repair, shortfall disclosed; retrieval >=50 met); P4-S03 PARTIALLY COMPLETE (no dry run) |
| 5 | 0 / 12 done (P5-S01, S02, S05 + new S06 to S09 + proposed S12 to S16) | NOT STARTED | 0 / 5 approved, all PARTIALLY COMPLETE: P5-S03 (decision made, shortfall disclosed); P5-S04 (local comparison done, n=12, one replicate; no code model); P5-S10 (opt-in, benefit UNPROVEN, blind validation not done); P5-S11 (conditional, gate not met, NOT TRIGGERED); P5-S17 (implemented, tested, wired as an opt-in; no live model run; benefit unproven) | see left |
| 6 | 0 / 2 done | NOT STARTED | 0 / 2 done (P6-S04 supporting only) | P6-S02 PARTIALLY COMPLETE (CI green on 64073ca, all four jobs; no host); P6-S03 IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |

When a phase starts, replace its count row with one row per step, as Phases 0–3 show.

**Status sync 2026-11-25 (Rafique's retrieval/analysis tasks).** P5-S06 IMPLEMENTED, TESTED (25 tests); P5-S07 IMPLEMENTED, TESTED (17 tests); P5-S08 DONE with a preregistered NO-GO (current BM25 + graph retained; ADR 0003 PROPOSED, decision blank; dense/hybrid code kept as the opt-in research module `traceforge/retrieval_next`); P5-S09 NOT STARTED, NOT TRIGGERED; P5-S12 IMPLEMENTED, TESTED (ranker NO-GO); P5-S15 IMPLEMENTED, TESTED (GO on fixtures); P5-S16 reduced suite IMPLEMENTED (23 fixtures; second-reviewer label check open); P5-S13, S14 NOT STARTED. These stay Rafique's. Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; ownership unchanged. Ruhan's P5-S11 is conditional, gate not met (NOT TRIGGERED); P5-S17 is implemented and opt-in wired (no live model run). Nothing is Reviewed or Approved, so the 'done' counts above are unchanged. Evidence: `RAFIQUE_HANDOFF.md` section 10.

New Phase 5 tasks (24 Nov 2026, all NOT STARTED at the time): P5-S06, P5-S07, P5-S08 (essential), P5-S09 (optional), all Rafique; P5-S10 (essential-optional, needs owner approval), P5-S11 (conditional on P5-S08 go), both Ruhan. Counts above include them (Rafique 23 primary after this addition; Ruhan stays at 20 primary: the P5-S10 and P5-S11 additions are in the 20, an earlier figure of 22 was wrong).

New Phase 5 tasks (25 Nov 2026, all NOT STARTED at the time, PROPOSED pending owner approval Q18): P5-S12 (MVP), P5-S13 (Tier 2), P5-S14 (Tier 2), P5-S15 (MVP), P5-S16 (MVP reduced set; Ruhan verifies labels), all Rafique; P5-S17 (conditional, RC2) Ruhan with Rafique supporting. Counts: Rafique 28 primary (the 27 listed in section 2.1 plus P0-S06 Part A); Ruhan 20 primary (P5-S17 is in the 20; the earlier figure of 23 was wrong).

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
4. **Steps (primary):** P0-S01, P0-S02, P0-S05, P0-S06 (Part A), P1-S01, P1-S02, P1-S03, P2-S01, P2-S02, P2-S03, P2-S07, P3-S01, P3-S02, P4-S02, P5-S01, P5-S02, P5-S05, P5-S06, P5-S07, P5-S08, P5-S09, P5-S12, P5-S13, P5-S14, P5-S15, P5-S16, P6-S01, P6-S04.
5. **Technical responsibilities:** FastAPI app core; Docker Compose lab design; Docker SDK and container isolation; pytest-based validators; fault mutation templates; Python `ast`; networkx graph; BM25 ranking; IR metrics (Recall@K, MRR, nDCG); bootstrap and McNemar statistics; security tests.
6. **Deliverables:** running lab with contracts; sandbox runner; ≥144 validated, frozen cases + ≥30 dev; evidence collector; code graph; L/G retrieval and E1 results; metrics + rule baseline; failure analysis; A4 statistics; security suite; paper method/data/evaluation sections.
7. **Knowledge needed:** Docker/Compose networking and resource limits, Python AST, information retrieval, basic statistics.
8. **Depends on Ruhan for:** `AgentRunRecord`s from the runner (P3-S04) to compute repair/diagnosis metrics; agent CLI for Sync 2 (P2-S07).
9. **Reviews:** all Track B PRs (P0-S03, P1-S04, P1-S05, P1-S06, P2-S04, P2-S05, P2-S06, P3-S03, P3-S04, P4-S01, P4-S03, P5-S03, P5-S04, P5-S10, P5-S11, P5-S17, P6-S02, P6-S03) and the proposal (P0-S04).

### 2.2 Muhammad Ruhan Kamran
1. **Role:** Track B, agent side.
2. **Ownership:** everything from context to diagnosis, patch, verified outcome, report, review and the user-facing app.
3. **Phases:** 0, 1, 2, 3, 4, 5, 6.
4. **Steps (primary):** P0-S03, P0-S04, P1-S04, P1-S05, P1-S06, P1-S07, P2-S04, P2-S05, P2-S06, P3-S03, P3-S04, P4-S01, P4-S03, P5-S03, P5-S04, P5-S10, P5-S11, P5-S17, P6-S02, P6-S03.
5. **Technical responsibilities:** SQLAlchemy models, Alembic, state machine; OpenAI-compatible client, tool schemas, caching, rate limits; prompt design; unified-diff parsing and git worktrees; GitHub REST; React/TypeScript UI; GitHub Actions; deployment.
6. **Deliverables:** incident API; gateway + ADR 0001; pipeline agent; repair loop with F0/F1 and no-leak test; report/review; GitHub intake; reviewer UI; experiment runner + results page; A3 experiment runs; demo and submission pack; A4 factorial runs and model comparison; CI and public deployment; paper system/agent sections and investor pitch; updated proposal.
7. **Knowledge needed:** FastAPI/SQLAlchemy, LLM tool calling, prompt engineering, git internals, React.
8. **Depends on Rafique for:** contracts (P0-S05, shared); sandbox runner (P1-S02) for P2-S04 (uses a fake runner until then); real cases (P1-S03) for Sync 1; real evidence/context (P2-S01, P2-S03) for Sync 2; frozen manifest (P3-S01) for test-split runs; metrics (P3-S02) for the results page.
9. **Reviews:** all Track A PRs (P0-S02, P1-S01…S03, P2-S01…S03, P3-S01, P3-S02, P4-S02, P5-S01, P5-S02, P5-S05, P5-S06, P5-S07, P5-S08, P5-S09, P5-S12 to P5-S16, P6-S01) and the label peer-check in P3-S01.

## 3. Individual task checklists

### Muhammad Rafique
- [ ] [P0-S01](phase-0-foundation/step-01-repository-and-collaboration-setup.md) Repository and collaboration setup
- [x] [P0-S02](phase-0-foundation/step-02-backend-scaffold.md) Backend scaffold (TRAC-1)
- [x] [P0-S05](phase-0-foundation/step-05-shared-contracts.md) Shared contracts, primary owner (TRAC-4)
- [ ] [P0-S06](phase-0-foundation/step-06-feasibility-prototype.md) Feasibility prototype, Part A: retrieval spike
- [ ] [P1-S01](phase-1-core-components/step-01-lab-fixtures.md) Lab fixtures (TRAC-5)
- [ ] [P1-S02](phase-1-core-components/step-02-sandbox-test-runner.md) Sandbox test runner (TRAC-6)
- [x] [P1-S03](phase-1-core-components/step-03-fault-generator-and-seed-cases.md) Fault generator + 4 seed cases (TRAC-7)
- [ ] [P2-S01](phase-2-evidence-to-repair/step-01-evidence-collector.md) Evidence collector (TRAC-12)
- [ ] [P2-S02](phase-2-evidence-to-repair/step-02-code-graph.md) Code graph (TRAC-13)
- [ ] [P2-S03](phase-2-evidence-to-repair/step-03-retrieval-l-and-g.md) Retrieval L and G + E1 (TRAC-14)
- [ ] [P2-S07](phase-2-evidence-to-repair/step-07-sync-2-full-pipeline.md) Sync 2, primary owner (TRAC-18)
- [x] [P3-S01](phase-3-dataset-evaluation-ui/step-01-dataset-scale-up-and-freeze.md) Dataset scale-up and freeze (TRAC-19)
- [ ] [P3-S02](phase-3-dataset-evaluation-ui/step-02-evaluation-metrics-and-baseline.md) Metrics + rule baseline (TRAC-20)
- [ ] [P4-S02](phase-4-a3-delivery/step-02-failure-analysis-and-results.md) Failure analysis and results (TRAC-23)
- [ ] [P5-S01](phase-5-research-completion/step-01-deeper-graph.md) Deeper graph (TRAC-24)
- [ ] [P5-S02](phase-5-research-completion/step-02-statistics.md) Statistics (TRAC-25)
- [ ] [P5-S05](phase-5-research-completion/step-05-bugsinpy-subset.md) BugsInPy subset, optional (TRAC-27)
- [x] [P5-S06](phase-5-research-completion/step-06-retrieval-benchmark-and-baselines.md) Retrieval benchmark + baselines RET-L / RET-G (essential) — COMPLETED 25 Nov (reviewed and reproduced by Rafique; label second check open)
- [ ] [P5-S07](phase-5-research-completion/step-07-incremental-index-and-embedding-cache.md) Incremental chunk manifest, embedding cache, verifier (essential) — IMPLEMENTED, TESTED; not reviewed by Rafique
- [ ] [P5-S08](phase-5-research-completion/step-08-embedding-retrieval-and-fusion.md) Embedding retrieval + fusion arms, ADR 0003 (essential, decision gate) — DONE, preregistered NO-GO; not reviewed by Rafique
- [ ] [P5-S09](phase-5-research-completion/step-09-optional-reranking.md) Optional reranking (optional) — NOT STARTED, NOT TRIGGERED
- [ ] [P5-S12](phase-5-research-completion/step-12-bidirectional-traversal-and-root-cause-ranker.md) Traversal overlay + root-cause ranker (MVP, proposed) — IMPLEMENTED, TESTED (ranker NO-GO); not reviewed by Rafique
- [ ] [P5-S13](phase-5-research-completion/step-13-config-value-flow-analysis.md) Config value-flow analysis (Tier 2, proposed) — NOT STARTED
- [ ] [P5-S14](phase-5-research-completion/step-14-runtime-evidence-fusion.md) Runtime evidence fusion (Tier 2, proposed) — NOT STARTED
- [ ] [P5-S15](phase-5-research-completion/step-15-change-impact-report-and-test-selection.md) Change-impact report + test selection (MVP, proposed) — IMPLEMENTED, TESTED (GO on fixtures); not reviewed by Rafique
- [ ] [P5-S16](phase-5-research-completion/step-16-root-cause-and-impact-evaluation-suite.md) Root-cause and impact evaluation suite (MVP reduced set; Ruhan verifies labels, proposed) — reduced suite IMPLEMENTED; not reviewed by Rafique
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
- [ ] [P5-S10](phase-5-research-completion/step-10-rc2-pipeline-robustness.md) RC2 candidate: pipeline robustness fixes (essential-optional, owner approval needed)
- [ ] [P5-S11](phase-5-research-completion/step-11-conditional-hybrid-experiment.md) Conditional hybrid experiment (conditional on P5-S08 go; supporting member Rafique) — conditional, gate not met, NOT TRIGGERED; adapter and preregistration validator exist
- [ ] [P5-S17](phase-5-research-completion/step-17-regression-aware-repair-validation.md) Regression-aware repair validation (conditional on owner approval, P5-S10, S15/S16 benefit; supporting member Rafique) — implemented, tested, opt-in wired; no live model run; not reviewed
- [ ] [P5-S16 label verification](phase-5-research-completion/step-16-root-cause-and-impact-evaluation-suite.md) Independent check of hand-labelled expected relationships (supporting; P5-S16 stays Rafique's)
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
| 5 | P5-S01 3 · P5-S02 2 · P5-S05 2.5 · P5-S06 1.5 · P5-S07 2 · P5-S08 2 · P5-S09 1 (optional) · P5-S12 3 · P5-S13 3 · P5-S14 1.5 · P5-S15 2.5 · P5-S16 3 (MVP reduced 1.5) = **27** | P5-S03 3 · P5-S04 2 · P5-S10 2 · P5-S11 2 (conditional) · P5-S17 3 (conditional) = **12** |
| 6 | P6-S01 2.5 · P6-S04 2.5 (half of paper) = **5** | P6-S02 3 · P6-S03 2.5 · P6-S04 2.5 = **8** |
| **Total** | **62** | **48.5** |

**Analysis**
- Totals are within 3% of each other. By phase they differ, by design: Rafique carries more in Phase 2 (graph + retrieval is the research core), Ruhan carries more in Phase 6 (CI, deployment, UI polish).
- **Rafique's Phase 2 is the critical path** (P2-S01 → P2-S03 blocks Sync 2). If it slips, Ruhan picks up P2-S07's wiring work (he owns the consuming side anyway) and Rafique keeps P2-S03.
- **Ruhan's Phase 2 has ~3 days of slack.** Use it to start P3-S03 (UI) early against contract samples, which reduces Phase 3 risk.
- The 24 Nov 2026 additions (P5-S06 to P5-S11) add 6.5 d to Rafique and 4 d to Ruhan; the old totals were 42.5 / 41.5. About 4 d of that is optional or conditional (P5-S09, P5-S11, and P5-S10 needs owner approval). Rafique's extra load is the open question Q16 (capacity/timeline); P5-S09 and P5-S05 are the first to drop.
- The 25 Nov 2026 additions (P5-S12 to P5-S17, PROPOSED) add 13 d to Rafique (full set; the MVP part is S12 + S15 + S16-reduced = 7 d) and 3 d (conditional) to Ruhan; totals before were 49 / 45.5 (after the 24 Nov additions). Rafique's total new study work is about 19.5 d full and about 12.5 d MVP (S06, S07, S08, S12, S15, S16-reduced). Capacity and timeline are an owner/Rafique decision (Q18); all effort figures are ASSUMPTION, not measured.
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
| P5-S11 Conditional hybrid experiment | Ruhan | Rafique (retrieval wiring) | Rafique | Only after the P5-S08 go decision and owner spend approval | New run directories, analysis note |
| P5-S16 label verification | Rafique | Ruhan (independent verifier of hand-labelled relationships) | Ruhan | Fixtures and derivations committed before any run | Verified labels |
| P5-S17 Regression-aware repair validation (conditional) | Ruhan | Rafique (impact/selection interface) | Rafique | Only with owner approval, P5-S10 and S15/S16 benefit | RC2 records, new fingerprint |
| P6-S04 Paper | Rafique | Ruhan | Both | Section split listed in the step | Final PDF |

## 6. Ownership consistency
The owners above are the same in [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md), every phase README and every step document. Synverk is not used for this project (see README); the `TRAC-n` numbers are historical references only. Checked 2026-11-25: the owner columns match for Ruhan's 20 steps; the Rafique status cells were not independently re-verified.


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
| P3-S01 Dataset freeze | Rafique | Rafique (approved 23 Nov) | COMPLETED (was "not done" on 21 Nov) |
| Contract `AgentRunRecord` (B9, B13) | shared | Claude-assisted | additive change; **Rafique must review** |
All Ruhan-track steps: implemented by the Claude-assisted session for Ruhan; none is approved yet (only Ruhan approves). The checklist is `RUHAN_CHECKLIST.md`; the evidence audit is `RUHAN_AUDIT.md`.

### Note 2026-11-24: retrieval modernization tasks added
At the project owner's instruction of 2026-11-24, six tasks were added to Phase 5 as a follow-up study "Retrieval modernization": P5-S06 to P5-S09 to Rafique (retrieval, graph and metrics are his Track A), P5-S10 and P5-S11 to Ruhan (his pipeline, runner and agent modules). No existing task was reassigned or changed in status. Taha Ahmed owns nothing (D3). The production codeintel/retrieval code that P5-S06 and later steps build on was authored by Ruhan's Claude-assisted session and still awaits Rafique's review (`RAFIQUE_HANDOFF.md`). All tasks are conditional on frozen RC1 staying untouched (D36); P5-S06 to P5-S09 spend zero AxForge tokens. Design: `docs/research/retrieval-architecture-review.md`.

### Note 2026-11-25: root-cause and impact analysis tasks added (PROPOSED)
At the project owner's instruction, six tasks were added to Phase 5: P5-S12 to P5-S16 to Rafique (graph, retrieval and metrics are his Track A; Ruhan reviews and independently verifies P5-S16 labels) and P5-S17 to Ruhan (repair pipeline, conditional, RC2 only, Rafique supporting). All are NOT STARTED and pending owner approval (Q18); no existing task was reassigned or changed in status. MVP: P5-S12, S15, S16 (reduced). Tier 2: P5-S13, S14. Design: `docs/research/root-cause-impact-regression-design.md`. New code goes in new modules; frozen RC1 stays untouched.
