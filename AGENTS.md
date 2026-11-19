# AGENTS.md

Single source of truth for all working rules. Topic rules live in
`docs/invariants/` and plans in `docs/plans/`, per the routing below.

## Routing

```
AGENTS.md (this file — routing + meta rules)
    ↓
docs/docs/index.md (knowledge domain map)
    ↓
docs/domain/<project>/index.md (project-specific facts: architecture, chosen libs, phase status)
    ↓
docs/invariants/ (universal rules for your current stack/domain)
    ↓
specific rule doc (core.md, backend.md, frontend.md, security.md, tooling.md, processes.md)
    ↓
source code (ground truth)
    ↓
implementation
```

Project-specific facts (this repo's folder names, model choices, phase
status) belong in `docs/domain/<project>/index.md` — never in
`docs/invariants/`. Invariants are the rules that hold across every project;
domain docs are what's true about *this* one.

## Rules

All rules live in `docs/invariants/`. Pick the rule doc that matches your
current task — never load all of them.

| Task                             | Rule doc                        |
| --------------------------------- | -------------------------------- |
| Any task                          | `docs/invariants/core.md`       |
| FastAPI / backend                 | `docs/invariants/backend.md`    |
| Next.js / frontend                | `docs/invariants/frontend.md`   |
| Credentials, DB, ORM              | `docs/invariants/security.md`   |
| Package managers, Docker, paths   | `docs/invariants/tooling.md`    |
| Plans, ADRs, cadence, README      | `docs/invariants/processes.md`  |
| Data, training, eval, benchmarks  | `docs/invariants/ml.md`         |

This project's facts live in `docs/domain/<project>/index.md`.

`core.md` is always loaded: folder structure, file-size limits,
real-data-only, and the Ponytail ladder — rules that hold no matter what
you're building. Everything else loads on demand.

Tooling (package manager, language version) is recorded in
`docs/invariants/tooling.md` once it's chosen. A root `INSTRUCTIONS.md`, if
present, is history only: where it disagrees with this file or
`docs/invariants/`, these win.

## First run — bootstrapping the docs tree

If `docs/invariants/` (or a specific file in it), `docs/docs/index.md`, or
`docs/domain/<project>/index.md` don't exist yet, don't wait for them to be
handed over — generate them yourself, in this same first session:

1. Create `docs/docs/index.md` and whichever `docs/invariants/*.md` files
   the project's actual stack needs (`core.md` and `processes.md` always;
   `backend.md` / `frontend.md` / `security.md` / `tooling.md` only for the
   stacks actually in play — a Java app, for instance, skips frontend.md).
2. Write a `docs/invariants/<stack>.md` for any stack this hierarchy
   doesn't already cover (Java, Android, whatever's being built) — folder
   layout, build tool, test framework, the same kind of thing backend.md
   does for FastAPI.
3. For anything you can't infer (framework choice, build tool, test
   framework, folder convention), ask — don't guess and lock it in
   silently. Propose a first draft, get it confirmed, then write it.
4. Write `docs/domain/<project>/index.md` with whatever architecture and
   naming actually gets decided.
5. Once the tree exists, everything above applies exactly as if it had been
   there before this session — this is a one-time scaffold, not a standing
   excuse to skip checking docs later.

If `docs/domain/<project>/index.md` (or an old INSTRUCTIONS.md-style file)
already exists with real content, don't regenerate over it — read it first
and ask before replacing anything.

## Never go exploring

For anything related to a repo, check the docs first — that's what they're for.

Go into source only when: (1) the docs don't answer, (2) the user explicitly
asks for implementation details, or (3) the task is to implement and the
docs say to do X — verify X in the source first.

## Working one step at a time

This shape is fixed and always active — no need to load `processes.md` just
to know it:

0. Sync first. Before any work, `git fetch` and check whether the local
   branch is behind `origin`; if it is, pull to the latest (`git pull
   --ff-only`) before touching anything.
1. Work ONE step at a time. The step is one step document in
   `docs/plans/phase-*/` (task ID `P<n>-S<nn>`): read it first and tell the
   user its ID and path before coding. The docs are the current plan; the
   Synverk board is not used for this project. `docs/adrs/` holds the
   decisions. Where a step document and an ADR disagree, say so.
2. Test it yourself before handing off. Fix obvious errors yourself — don't
   hand basic issues back to the user.
3. Note anything else you notice along the way (UI gaps, config, missing
   checks). Flag it to the user rather than silently fixing it or silently
   skipping it — keep a running list so nothing gets lost.
4. Hand off in plain language — what changed, why, what the user will
   notice — for both frontend and backend, plus the exact terminal commands
   so the user can verify it themselves.
5. Wait for explicit approval before starting the next step. Set the step
   document's Status to NEEDS REVIEW and give the check output in chat. The
   user is the project owner and approves it in chat; the agent never
   approves its own step.
6. Log the step in that day's `.memory/tasks.md` (format in `processes.md`)
   so progress is visible without re-deriving it from chat history.

This is what gives a visible timetable: `docs/plans/` (step Status lines
and `TEAM_WORK_DISTRIBUTION.md`) is the "what's next," and
`.memory/tasks.md` is the running "what's done" — both are cheap
to skim, so where things stand is never buried in scrollback.

## Session-level rules

- Capture fixes where they belong. When the user asks to fix/change
  something, add the rule to the invariants doc that owns that topic — not
  by dumping everything into AGENTS.md. Only routing/meta-level changes
  belong here. Note the change (what, why, how to revert) in that day's
  `.memory/tasks.md`.
- Session continuity. Once a doc is loaded this session, its rules apply
  for the rest of the session — no re-reading needed.
- Destructive actions. Always confirm before pushing, deleting, or
  rebuilding containers.
- Commits. The agent commits a step itself once the user has approved it,
  and pushes that branch to `origin` straight after. Never commit or push unapproved work. Merging into `main`,
  force-pushing and tagging still need a yes each time.
- Co-author. Never add the AI/agent's name as co-author.

## Git

One commit per approved unit of work — a single step, or an explicitly
batched group of steps done together. Never split one approved batch into
several commits, and never fold unrelated work into one commit.

- Subject under 72 characters, self-explanatory without a body — e.g.
  `chore(setup): scaffold dependencies and feature structure`.
- Covers only what this commit's diff actually changes. Never re-lists
  earlier or already-committed work.
- No bulleted essays in the body.

The agent states the message and runs the commit after approval. No
co-author or "generated with" lines for the agent, ever.

## Skills

- Frontend UX review/polish/audit → **impeccable**.
- Visual redesign/overhaul (new look, whole-screen redesign) →
  **ui-ux-pro-max**. Don't mix these two up.
- Backend security implementation or review → **backend-security-coder**
  (vs a general security-auditor: this one writes secure code, it doesn't
  do high-level audits).
- Simplest solution, shortest working diff → **Ponytail**, active by
  default for all code writing (full ladder in `core.md`).
- If a required skill isn't installed, tell the user how to install it and
  offer to do it for them.
