# TraceForge execution plan

TraceForge takes a reproducible failure in a Dockerized Python service and works out *why* it failed. It collects read-only evidence, links that evidence to the exact code symbols and config keys, diagnoses the root cause (or honestly abstains), proposes a minimal patch, and checks the patch against hidden tests in a sandbox. An engineer approves or rejects the frozen patch; nothing is deployed.

This folder is the team's execution manual: what to build, why, how, who owns it, in what order, how it is tested, and when it counts as done.

## Where things stand (19 November 2026)
- **Implemented and verified:** public repo `Rafique610/traceforge`, `main` protected against force push and deletion (no approving review required), docs rules tree (`docs/invariants/`, `docs/domain/`), this execution manual merged to `main`.
- **Not implemented:** all application code. Every step below is NOT STARTED unless its document says otherwise.
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
| 5 Research completion | [phase-5-research-completion](phase-5-research-completion/README.md) | A4 | P5-S01 … P5-S05 |
| 6 Productization and paper | [phase-6-productization-paper](phase-6-productization-paper/README.md) | A4 | P6-S01 … P6-S04 |

## Task IDs
- Task IDs are `P<phase>-S<step>`, e.g. `P2-S03`. The same ID is used in every document.
- **The docs are the plan; Synverk is not used for this project.** The step document is both the how-to and the live status. The `TRAC-n` numbers in step documents and the [card map](IMPLEMENTATION_ROADMAP.md#task-to-card-map) are historical references only. Steps that mention a Synverk card, proof or comment: use the step document's Status line and the PR description instead.
- **No peer approval needed.** Where a step says "reviewed by" or "both approve", read it as *optional* review; either member may merge their own work when they judge it ready.

## How to track progress
0. `git fetch origin`; if your branch is behind, `git pull --ff-only` before anything else.
1. Pick the next step in your lane from [TEAM_WORK_DISTRIBUTION.md](TEAM_WORK_DISTRIBUTION.md). Check its prerequisites are done.
2. Set its Status to IN PROGRESS; create the branch named in the step document from an up-to-date `main`.
3. Tick checklist boxes in the step document **in the same commit as the work** (`[ ]` → `[x]`). Only tick what is actually done and verified.
4. Change the step's **Status** line: NOT STARTED → IN PROGRESS → NEEDS REVIEW → COMPLETED (or BLOCKED with a reason).
5. Merge to `main` (directly or via a self-merged PR) when you judge it ready; the other member may review afterwards.
6. After merge, update the status column in the phase README and your row in TEAM_WORK_DISTRIBUTION.md.

Status labels used everywhere: **NOT STARTED, IN PROGRESS, BLOCKED, NEEDS REVIEW, COMPLETED**.
