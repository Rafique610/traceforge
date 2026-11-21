# Processes

## Sync before work
- Before starting any work: `git fetch origin`, then `git status -sb`. If `main` is behind `origin/main`, `git pull --ff-only` first. Work happens on `main`.

## Steps
- The plan is the execution manual in `docs/plans/` (phase folders, one step document per task, IDs `P<n>-S<nn>`). Synverk is not used for this project; the TRAC-n numbers in step documents are historical references only.
- Work one step at a time. Read the step document first, tell the user its ID and path, then code.
- Before handoff: test it yourself, fix obvious errors, update README, then explain in plain language (backend and frontend) what changed and what the user will notice, with exact commands to verify.
- Keep a running list of things noticed but not done; flag them, never fix or skip silently.
- Track status in the step document (Status line + checklist) and the phase README. Set NEEDS REVIEW and give the check output in chat. Only the user approves. Wait for approval before the next step.

## Commits and merging
- **No pull requests and no step branches.** After approval, commit on `main` and push straight to `origin/main`. Both members pull to see what changed (sync rule above).
- **Before every commit** (by either member or the agent), update `docs/plans/TEAM_WORK_DISTRIBUTION.md` section 0 "Progress at a glance" for **both** members: done counts, working on, next up, waiting on, the per-step status rows, and the "Last updated" line. Tick the section 3 checklist items this commit finishes. The update goes in the same commit, so both people see progress side by side without asking.
- One commit per approved step (or explicitly batched group). Subject under 72 chars, e.g. `feat(retrieval): add BM25 baseline`. Covers only that diff. No bulleted essay body.
- Never add an AI/agent co-author or "generated with" line.
- No peer approval is required. The other member checks the work after pulling and fixes or follows up if needed. If a push is rejected because `origin/main` moved, `git pull --rebase` and push again; never force-push.
- `main` still blocks force pushes and deletion. For the agent: force-pushing and tagging need a yes each time.

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
