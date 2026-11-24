# Project overview

## Problem statement
Teams running Python services in Docker see the same symptom for unrelated reasons. "Connection refused" can mean a wrong hostname in config, code reading the wrong setting, or a database that is genuinely down. An HTTP 500 can be a code defect or a config pointing at an empty database. Logs, dashboards and code search each show a piece; engineers join them by hand, guess a fix, and rerun tests. Coding assistants can edit code but don't see the runtime evidence; monitoring sees the symptom but can't propose or verify a fix.

## What TraceForge does
Given a reproducible failure, TraceForge:
1. collects read-only evidence (container state, logs, redacted effective config, tracebacks) pinned to an exact Git SHA;
2. links that evidence to code symbols and config keys through a provenance-carrying dependency graph;
3. retrieves a small, cited context for a coding LLM;
4. diagnoses one of four outcomes: `configuration`, `application_code`, `runtime_dependency` (diagnose only, no patch) or `insufficient_evidence` (abstain);
5. for repairable outcomes, generates a minimal diff and tests it in a sandbox: the bug must reproduce before the patch and hidden, pre-written tests must pass after it;
6. produces an evidence-linked report; an engineer approves or rejects the exact patch hash. Nothing is deployed.

## Research question (R&D Product track)
Does evidence-bound graph retrieval improve root-cause localization and independently verified repair over lexical retrieval, and what does iterative test feedback add? Answered with a 2×2 design (graph on/off × feedback on/off) on a frozen, labelled dataset. Details: [ARCHITECTURE.md](ARCHITECTURE.md#research-design).

## Objectives
| # | Objective | Measured by |
|---|---|---|
| O1 | Working end-to-end product for config and Python code faults | Demo: failure → report → review, through UI, API, DB, LLM, sandbox |
| O2 | Honest diagnosis, including abstention and dependency outages | Cause-class accuracy, abstention precision on dedicated cases |
| O3 | Independently verified repairs | Verified repair rate with hidden tests |
| O4 | A controlled answer to the research question | E1 retrieval metrics; L0 vs G0 (A3); full 2×2 with CIs (A4) |
| O5 | Zero-cost operation | Mistral free tier + local Ollama; no paid API |

## Target users
- **Primary:** backend engineers maintaining Python services on Docker Compose who triage failures.
- **Secondary:** reviewers/instructors auditing why a diagnosis or patch was accepted.
- **Not targeted:** SREs needing fleet-wide production automation.

## Core functionality (Assignment 3 slice)
- Create an incident from a lab fault case or a GitHub issue.
- Evidence timeline, ranked code/config hits with reasons, hypotheses with supporting/contradicting evidence.
- Diff plus red/green test results; approve/reject bound to the patch hash.
- Results page: retrieval, diagnosis and repair metrics from saved runs.

## Scope
**In scope:** configuration faults and Python application-code faults in a Docker Compose lab (`shop-api`, `worker`, Postgres, Redis); read-only infrastructure evidence; single pipeline agent; sandbox verification; reviewer UI; GitHub issue intake; evaluation harness.

**Out of scope:** production deployment or automated recovery; infrastructure repair; multi-agent orchestration; MoE/SSD expert offloading; fine-tuning; languages other than Python; Kubernetes.

## Expected final outcome
- **Assignment 3:** a working vertical slice (~43% of the product) plus initial quantitative evaluation: ≥50 labelled held-out examples per AI component, baselines, ≥10 failure analyses, latency/cost, first R&D result (E1 and L0 vs G0).
- **Assignment 4:** the full product, full 2×2 with 3 replicates and statistics, model comparison, CI and public deployment, research paper and investor pitch.

## Team
| Member | Roll no. | Track |
|---|---|---|
| Muhammad Rafique | 23i-0747 | Track A, evidence side (repo owner) |
| Muhammad Ruhan Kamran | 23i-0062 | Track B, agent side |

Supervisor: Sir Akhtar Jamil. Taha Ahmed appears in the earlier proposal but is no longer on the team.

## Current status

**Update 2026-11-25:** the table below is the 19 Nov snapshot and is stale (code now exists: backend, frontend, lab, dataset, agent, evaluation). Current status: `RUHAN_TASK_TRACKER.md` and `TEAM_WORK_DISTRIBUTION.md` section 0. The 18 Nov supervisor email is conditional written permission to proceed ("You may proceed with the project after incorporating the recommended changes"); it is not written approval of the revised scope or a sign-off, and the noted verbal approval is not a written document (evidence: `D:\TraceForge\Assignment_3_TraceForge\Evidence\`). Taha Ahmed is off the team and owns nothing.
Verified by repository and board inspection on 19 November 2026:

| Item | State |
|---|---|
| GitHub repo, `.gitignore`, README, AGENTS.md | Implemented and verified (commit f98586e) |
| Docs rules tree (`docs/invariants`, `docs/domain`, `docs/docs/index.md`) | Implemented and verified (e1b7890) |
| Branch protection on `main` | Implemented and verified |
| Research safeguards in plan | Written; PR #1 open, awaiting Ruhan's review |
| Ruhan as GitHub collaborator / Synverk member | Not done (collaborators: Rafique610 only; Synverk project has no members) |
| Backend, frontend, lab, dataset, agent, evaluation | Planned, not implemented (no source code exists) |
| Supervisor approval of revised scope | 19 Nov snapshot. Conditional written permission to proceed received 18 Nov (email); written confirmation of the revised scope not on disk (P0-S04) |
| Primary model ID and Mistral free-tier limits | Not decided (P1-S05) |
