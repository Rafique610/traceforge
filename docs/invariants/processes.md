# Processes

## Sync before work
- Before starting any work: `git fetch origin`, then `git status -sb`. If the branch is behind `origin`, `git pull --ff-only` first. Start a new step branch from an up-to-date `main`.

## Steps
- The plan is the execution manual in `docs/plans/` (phase folders, one step document per task, IDs `P<n>-S<nn>`). Synverk is not used for this project; the TRAC-n numbers in step documents are historical references only.
- Work one step at a time. Read the step document first, tell the user its ID and path, then code.
- Before handoff: test it yourself, fix obvious errors, update README, then explain in plain language (backend and frontend) what changed and what the user will notice, with exact commands to verify.
- Keep a running list of things noticed but not done; flag them, never fix or skip silently.
- Track status in the step document (Status line + checklist) and the phase README. Set NEEDS REVIEW and give the check output in chat. Only the user approves. Wait for approval before the next step.

## Commits and merging
- After approval the agent commits the step and pushes the branch to `origin`.
- One commit per approved step (or explicitly batched group). Subject under 72 chars, e.g. `feat(retrieval): add BM25 baseline`. Covers only that diff. No bulleted essay body.
- Never add an AI/agent co-author or "generated with" line.
- No peer approval is required. Either member may merge their own work into `main` (directly or via a self-merged PR) when they judge it ready; the other member fixes or follows up afterwards if needed. A PR review by the other member is welcome but optional.
- `main` still blocks force pushes and deletion. For the agent: merging into `main`, force-pushing and tagging need a yes each time.

## README
- Update `README.md` on every step: new capabilities, paths and commands. Every commit carries an up-to-date README.

## ADRs
- A decision that changes stack, scope, research design or data goes in `docs/adrs/NNNN-title.md`: context, decision, consequences, how to revert.

## Daily memory log (`.memory/`, git-ignored)
- One file per day: `.memory/<DD-month-YYYY>/tasks.md`, appended in order.
- Header: one-line day verdict and a bold summary (X done / Y approved / Z changed).
- Task table row: what, status (✅ Approved / 🔄 In progress / ⚠️ Needs changes), and enough detail to reverse it (files, names, exact change).
- Timestamps from the real clock, 12-hour with zone and UTC: `1:48 AM (UTC+05:00 · 20:48 UTC)`. Never guess; mark unknown ones `(~ approx.)`.
- A separate section lists every rule change that day: what changed, why (the user's words), how to revert.
