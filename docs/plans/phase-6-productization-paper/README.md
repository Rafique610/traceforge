# Phase 6 — Productization and paper (Assignment 4)

**Status:** IN PROGRESS (status sync 2026-11-25: P6-S02 partial, P6-S03 implemented and tested)

## Phase information
- **Purpose:** meet Assignment 4's engineering requirements (containerisation, CI/CD, public deployment, AI tool declaration) and produce the research paper and investor pitch.
- **Objectives:** a security test suite that fails if any guard is removed; CI on every PR; two-stage images; a public link for the reviewer app; a polished UI with an audit view and experiment comparison; the paper and pitch built from saved results.
- **Scope:** product hardening and written outputs. No new research experiments.
- **Expected outcome:** milestone **M6**: Assignment 4 submission.
- **Prerequisites:** M4; P5-S02 and P5-S03 results for the paper and comparison view.

## Task overview
| Step ID | Task | Responsible | Dependencies | Status |
|---|---|---|---|---|
| [P6-S01](step-01-security-hardening.md) | Security hardening (TRAC-26) | Rafique | P4-S03 | NOT STARTED |
| [P6-S02](step-02-ci-and-deployment.md) | CI, images, public deployment (TRAC-30) | Ruhan | P4-S03 | PARTIALLY COMPLETE (no GitHub run, no host) |
| [P6-S03](step-03-ui-polish-and-audit-view.md) | UI polish + audit view (TRAC-31) | Ruhan | P4-S03, P5-S02 | IMPLEMENTED, TESTED; NOT REVIEWED/APPROVED |
| [P6-S04](step-04-paper-and-pitch.md) | Paper, documentation, investor pitch (TRAC-32) | Rafique (+Ruhan) | P5-S02, P5-S03 | NOT STARTED |

## Execution order
- P6-S01 and P6-S02 can start right after A3 delivery, in parallel with Phase 5 runs (which are mostly unattended wall-clock time).
- P6-S02 should land early: once CI is a required check on `main`, every later PR benefits.
- P6-S03's comparison view needs P5-S02 output; the audit view does not.
- P6-S04 last; drafting of sections not depending on final numbers (intro, related work, system description) can start any time.

## Deliverables
`tests/security/` suite; `.github/workflows/ci.yml`; two-stage Dockerfiles for backend and frontend; public deployment + ADR; polished UI; paper PDF, documentation, pitch deck.

## Completion criteria
- [ ] Security suite in `task test`; each test fails when its guard is removed
- [ ] CI required on `main` and green
- [ ] Public link works and shows saved runs/reports
- [ ] Audit and comparison views with screenshots
- [ ] Paper reviewed by both; every number traceable to saved runs; references re-verified
- [ ] Pitch deck from the Lean Canvas

## Handoff
Final submission; tag `a4-submission` after explicit approval.

## Navigation
- [P6-S01 Security hardening](step-01-security-hardening.md)
- [P6-S02 CI and deployment](step-02-ci-and-deployment.md)
- [P6-S03 UI polish and audit view](step-03-ui-polish-and-audit-view.md)
- [P6-S04 Paper and pitch](step-04-paper-and-pitch.md)
- Previous: [Phase 5](../phase-5-research-completion/README.md) · [Plans README](../README.md)
