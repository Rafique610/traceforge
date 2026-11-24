# TraceForge execution plan

TraceForge takes a reproducible failure in a Dockerized Python service and works out *why* it failed. It collects read-only evidence, links that evidence to the exact code symbols and config keys, diagnoses the root cause (or honestly abstains), proposes a minimal patch, and checks the patch against hidden tests in a sandbox. An engineer approves or rejects the frozen patch; nothing is deployed.

This folder is the team's execution manual: what to build, why, how, who owns it, in what order, how it is tested, and when it counts as done.

## Where things stand (status sync 25 November 2026)
- **Ruhan's 20 primary steps:** 0 COMPLETE & VERIFIED. 11 are IMPLEMENTED NOT VERIFIED (code and tests exist, Rafique has not reviewed, the owner has not approved), 7 are PARTIALLY COMPLETE, 2 are NOT STARTED and conditional (P5-S11, P5-S17). Per-task five-fact status (implemented / tested / integrated / reviewed / approved): [RUHAN_TASK_TRACKER.md](RUHAN_TASK_TRACKER.md). The older [RUHAN_AUDIT.md](RUHAN_AUDIT.md) is superseded.
- **Rafique's 28 primary steps:** see [TEAM_WORK_DISTRIBUTION.md](TEAM_WORK_DISTRIBUTION.md) section 0 (P0-S02, P0-S05, P1-S03, P3-S01 approved; the rest as listed there).
- **Evidence:** backend 983 passed / 21 skipped (before 25 Nov); frontend vitest 78; both Docker images build. No GitHub Actions run, no host, no public URL, no live Investigate run against a real provider, no clean-clone dry run.
- **Open human-only items:** written supervisor approval of the revised scope, Rafique's review, owner approval of steps, hosting decision (Q7), branch protection, the A3-protocol decision (supersede or extend the reduced evaluation in `results/final`).
- The step documents' older text ("All application code is NOT implemented") is history; read each step's Status line, which was synced for Ruhan's steps on 2026-11-25.
- Details: [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md#current-status).

## Recommended reading order
1. [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md): what and why.
2. [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md): what "working" means.
3. [ARCHITECTURE.md](ARCHITECTURE.md): how the parts fit.
4. [TEAM_WORK_DISTRIBUTION.md](TEAM_WORK_DISTRIBUTION.md): find your own task list.
5. [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md): the order of everything.
6. Your current phase README, then your step document.
7. [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) and [TESTING_AND_VALIDATION.md](TESTING_AND_VALIDATION.md) before any sync step.
8. [RISKS_AND_MITIGATION.md](RISKS_AND_MITIGATION.md) and [DECISIONS_AND_OPEN_QUESTIONS.md](DECISIONS_AND_OPEN_QUESTIONS.md) when something is unclear.

## General documents
| Document | Purpose |
|---|---|
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Problem, objectives, users, scope, current status |
| [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md) | Functional, non-functional, security, integration requirements and acceptance criteria |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data flow, APIs, database, trust boundaries, deployment |
| [TEAM_WORK_DISTRIBUTION.md](TEAM_WORK_DISTRIBUTION.md) | Who owns what, per-member checklists, workload balance |
| [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) | Every task in order, critical path, milestones |
| [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) | Contracts, integration order, sync checkpoints |
| [TESTING_AND_VALIDATION.md](TESTING_AND_VALIDATION.md) | Test levels, owners, success criteria |
| [RISKS_AND_MITIGATION.md](RISKS_AND_MITIGATION.md) | Risks with likelihood, impact, mitigation, owner |
| [DECISIONS_AND_OPEN_QUESTIONS.md](DECISIONS_AND_OPEN_QUESTIONS.md) | Confirmed decisions vs assumptions vs open questions; contradictions found |
| [end-to-end.md](end-to-end.md) | The original one-page plan (kept for history; this folder supersedes it) |

## Phases
| Phase | Folder | Assignment | Steps |
|---|---|---|---|
| 0 Foundation | [phase-0-foundation](phase-0-foundation/README.md) | A3 | P0-S01 … P0-S05 |
| 1 Core components | [phase-1-core-components](phase-1-core-components/README.md) | A3 | P1-S01 … P1-S07 |
| 2 Evidence-to-repair pipeline | [phase-2-evidence-to-repair](phase-2-evidence-to-repair/README.md) | A3 | P2-S01 … P2-S07 |
| 3 Dataset, evaluation and product surface | [phase-3-dataset-evaluation-ui](phase-3-dataset-evaluation-ui/README.md) | A3 | P3-S01 … P3-S04 |
| 4 Assignment 3 evaluation and delivery | [phase-4-a3-delivery](phase-4-a3-delivery/README.md) | A3 | P4-S01 … P4-S03 |
| 5 Research completion | [phase-5-research-completion](phase-5-research-completion/README.md) | A4 | P5-S01 … P5-S17 |
| 6 Productization and paper | [phase-6-productization-paper](phase-6-productization-paper/README.md) | A4 | P6-S01 … P6-S04 |

## Task IDs
- Task IDs are `P<phase>-S<step>`, e.g. `P2-S03`. The same ID is used in every document.
- **The docs are the plan; Synverk is not used for this project.** The step document is both the how-to and the live status. The `TRAC-n` numbers in step documents and the [card map](IMPLEMENTATION_ROADMAP.md#task-to-card-map) are historical references only. Steps that mention a Synverk card, proof or comment: use the step document's Status line and the PR description instead.
- **No peer approval needed.** Where a step says "reviewed by" or "both approve", read it as *optional* review; either member may merge their own work when they judge it ready.

## How to track progress
0. `git fetch origin`; if your branch is behind, `git pull --ff-only` before anything else.
1. Pick the next step in your lane from [TEAM_WORK_DISTRIBUTION.md](TEAM_WORK_DISTRIBUTION.md). Check its prerequisites are done.
2. Set its Status to IN PROGRESS. Work on an up-to-date `main` (no step branches; the Branch field in older step documents is ignored).
3. Tick checklist boxes in the step document **in the same commit as the work** (`[ ]` → `[x]`). Only tick what is actually done and verified.
4. Change the step's **Status** line: NOT STARTED → IN PROGRESS → NEEDS REVIEW → COMPLETED (or BLOCKED with a reason).
5. Commit on `main` and push straight to `origin/main` (no pull requests). The other member pulls and checks it.
6. **Before every commit**, update section 0 "Progress at a glance" in [TEAM_WORK_DISTRIBUTION.md](TEAM_WORK_DISTRIBUTION.md) for both members, in the same commit. After merge, update the status column in the phase README.

Status labels: **NOT STARTED, IN PROGRESS, BLOCKED, NEEDS REVIEW, COMPLETED**. For Ruhan's tasks (since 2026-11-25) the tracker uses five separate facts (implemented / tested / integrated / reviewed / approved) and the overall labels COMPLETE & VERIFIED, IMPLEMENTED NOT VERIFIED, PARTIALLY COMPLETE, NOT STARTED, BLOCKED. COMPLETE & VERIFIED requires review and approval.
