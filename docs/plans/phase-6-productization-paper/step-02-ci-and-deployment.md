# P6-S02 — CI, two-stage images and public deployment

## A. Task identification
| Field | Value |
|---|---|
| Phase | 6 Productization and paper |
| Step | 2 |
| Task ID | P6-S02 |
| Synverk card | TRAC-30 |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | — |
| Reviewer | Muhammad Rafique |
| Priority | Low (A4) |
| Effort | 3 days |
| Status | PARTIALLY COMPLETE (CI green on GitHub; no host, no public URL) |
| Branch | `ruhan/P6-S02-ci-deploy` |

**Status sync 2026-11-25 (final).** Evidence: interim checkpoint pushed to origin/main (commits up to 64073ca); the CI run on 64073ca is green on all four jobs (backend ruff+pytest, contracts, frontend, docker). Earlier failures fixed: ruff E501/I001, stale contract schemas regenerated, a test relying on a missing DB password env var made hermetic, CI/pnpm/drift-check fixes in `ci.yml`. Local docker build and compose up healthy (ADR 0002). Host (Q7) and public URL still open; branch protection is Rafique's. Five-fact detail: `docs/plans/RUHAN_TASK_TRACKER.md`.

## B. Objective
Meet Assignment 4's engineering requirements: containerisation, CI/CD and a public deployment, at zero cost.

## C. Prerequisites
- A3 delivered. Decide the free host (open question Q7) and whether the public app needs login.

## D. Technical background
- **What gets deployed publicly:** the reviewer app (API + UI + Postgres) in a **read-only showcase mode**: it serves saved runs, reports and the results page. The lab, sandbox and live LLM calls stay local (running untrusted repair loops on a public host would need much stronger isolation and paid compute).
- **CI:** GitHub Actions on PRs: ruff, backend unit tests, frontend tests, contract sample tests, security suite (Docker-dependent tests marked and run in a job with Docker available, or skipped with a clear reason). Integration tests replay from committed cache fixtures, so CI needs no API key.
- **Images:** two-stage Dockerfiles (`docs/invariants/tooling.md`).

## E. Implementation instructions
1. `.github/workflows/ci.yml`: jobs `lint`, `backend-tests`, `frontend-tests`, `security-tests`; cache uv and pnpm; run on `pull_request` and `push` to `main`.
2. Make CI a **required status check** on `main` (branch protection update — confirm with Rafique as owner).
3. `backend/Dockerfile` (uv build stage → slim runtime, non-root) and `frontend/Dockerfile` (pnpm build → static server stage); `compose.prod.yaml`.
4. Showcase mode setting (`TRACEFORGE_MODE=showcase`): disables investigate/review writes; loads saved runs and reports from a bundled export.
5. ADR `docs/adrs/000N-deployment.md`: chosen free host, why, limits, how to redeploy.
6. Deploy; add the link to README and the submission pack.
7. Optional CD: deploy on tag `a4-*`.

## F. Checklist
- [ ] CI workflow with four jobs
- [ ] CI required on `main`
- [ ] Two-stage backend and frontend images
- [ ] Production compose
- [ ] Showcase mode
- [ ] Deployment ADR
- [ ] Public link live
- [ ] README updated

## G. Expected deliverables
New: `.github/workflows/ci.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `compose.prod.yaml`, deployment ADR. Modified: `config.py`, README.

## H. Testing and validation
- A PR with a failing test is blocked by CI; a clean PR passes.
- Public link loads the results page and a saved report; write endpoints return 403 in showcase mode.
- Image sizes recorded (two-stage benefit).

## I. Dependencies and integration
- **Depends on:** P4-S03.
- **Feeds:** P6-S04 (deployment section), final submission.

## J. Definition of done
Merged after Rafique's review; CI required and green; public link working; ADR merged; TRAC-30 approved.
