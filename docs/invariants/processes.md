# Processes

## Steps and cards
- The plan lives in `docs/plans/end-to-end.md` as numbered steps. Each step becomes one Synverk card when work on it starts.
- Work one card at a time. Read the card first, tell the user its flow name and link, then code.
- Before handoff: test it yourself, fix obvious errors, update README, then explain in plain language (backend and frontend) what changed and what the user will notice, with exact commands to verify.
- Keep a running list of things noticed but not done; flag them, never fix or skip silently.
- Paste check output as a card comment, move the card to review. Only the user approves. Wait for approval before the next card.

## Commits
- After approval the agent commits the step and pushes the branch to `origin`.
- One commit per approved step (or explicitly batched group). Subject under 72 chars, e.g. `feat(retrieval): add BM25 baseline`. Covers only that diff. No bulleted essay body.
- Never add an AI/agent co-author or "generated with" line.
- Merging into `main`, force-pushing and tagging need a yes each time.

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
