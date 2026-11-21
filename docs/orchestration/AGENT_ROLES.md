# Agent roles (only those that earn their keep)

**Orchestrator** (main session) — owns the checklist, STATE.md, DECISIONS.md and all shared files (Taskfile.yml, README.md, main.py, config.py, pyproject.toml, docs/plans/TEAM_WORK_DISTRIBUTION.md). Single writer for shared files; does integration and final test runs.

| Role | May edit | Never edit | Reads | Deliverable / tests |
|---|---|---|---|---|
| Backend | `backend/traceforge/{incidents,reports,reviews,github}/**`, matching tests, own Alembic migrations | Rafique folders, contracts | step doc, invariants backend/core/security | endpoints + pytest |
| AI/LLM | `backend/traceforge/{agent,repair}/**`, tests | contracts, sandbox | gateway/agent step docs, security+ml invariants | gateway, agent, repair loop; mocked-provider, injection and no-leak tests |
| Frontend | `frontend/**`, web tasks in Taskfile | backend | frontend invariants, API schemas | Vitest + build |
| Research/Eval | `docs/research/**`, `spikes/model_probe/**`, `backend/traceforge/evaluation/{runner,conditions}/**` | metrics/baselines/analysis | ml invariants, P0-S06, P3-S04 | JSON results + report; no invented numbers |
| QA | tests only | source | acceptance criteria | targeted + milestone suites |
| Docs | `docs/guide/**`, README text handed over | code | verified facts only | encyclopedia in sync |
| Reviewer | read-only (`code-review` skill) | everything | the diff | findings |

Every parallel-agent prompt carries: task ID, owned paths, forbidden paths, step doc path, deliverables, test commands, "no commit". Agents report files, real test output, unverified items and any shared-file edits they need; the orchestrator applies those.
