# Decisions and open questions

Three kinds of entries, never mixed:
- **Confirmed:** decided by the team in conversation, written in repo docs, or set on the board.
- **Assumption:** reasonable default used for planning; must be confirmed or changed.
- **Open:** not decided; blocks or affects a step.

## Confirmed decisions
| # | Decision | Source |
|---|---|---|
| D1 | Scope: configuration and Python code faults only; infrastructure is read-only evidence; no production deployment; no MoE; no multi-agent; no fine-tuning | Supervisor review; `docs/domain/traceforge/index.md` |
| D2 | Track: R&D Product | Proposal; domain doc |
| D3 | Team: Muhammad Rafique and Muhammad Ruhan Kamran (Taha Ahmed no longer on team) | User, 19 Nov 2026 |
| D4 | Work split: Track A Rafique (evidence side), Track B Ruhan (agent side); separate folders; contracts shared | User approved; `end-to-end.md`; card titles |
| D5 | Budget USD 0: primary LLM Mistral free tier (pinned Devstral), comparator Qwen2.5-Coder-7B via Ollama, spare Groq | User choice |
| D6 | Repo public at `Rafique610/traceforge`; `main` blocks force push and deletion; **no approving review required**, either member may merge their own work (required review removed 19 Nov 2026) | User, 19 Nov 2026; verified via GitHub API |
| D7 | Frontend: Vite + React + TypeScript | User choice |
| D8 | Course PDFs and `INSTRUCTIONS.md` are git-ignored | `.gitignore` |
| D9 | Outcome classes: configuration, application_code, runtime_dependency (no patch), insufficient_evidence (abstain) | Domain doc; review fix |
| D10 | Fair design: trace anchoring in both retrieval arms; both feedback arms get 3 attempts; hidden tests run once and never feed back | Domain doc; review fixes |
| D11 | Five safeguards: distance labels, pipeline-first agent, rule baseline, LLM response cache, freeze before tuning | User approved; PR #1 |
| D12 | AI components evaluated: retrieval, diagnosis, repair; report is a deterministic template | Domain doc |
| D13 | Tooling: Python 3.12 + uv, pnpm, pytest/Vitest, ruff, Taskfile, Docker Compose | `docs/invariants/tooling.md` |
| D14 | DB access via SQLAlchemy 2 + Alembic (agent chose; user had no preference) | `docs/invariants/backend.md` |
| D15 | Dataset targets: ≥60 config, ≥60 code, ≥12 runtime_dependency, ≥12 insufficient_evidence held-out; ≥30 dev | Domain doc; TRAC-19 |
| D16 | The docs in `docs/plans/` are the plan; Synverk is not used for this project (TRAC-n kept as references) | User, 19 Nov 2026 |
| D17 | Before any work, fetch and pull `main`/the current branch if it is behind `origin` | User, 19 Nov 2026; `docs/invariants/processes.md` |

## Assumptions (to confirm)
| # | Assumption | Used in | Confirm by |
|---|---|---|---|
| AS1 | Effort estimates in person-days are planning guesses | Roadmap, team doc | Re-estimate after Phase 1 |
| AS2 | Only Track B writes Alembic migrations; Track A returns contract objects | Integration plan | Both, at P0-S05 |
| AS3 | Run records stored as JSON files under `runs/` (git-ignored) for A3 | P3-S04 | Ruhan at P3-S04 |
| AS4 | Graph and LLM cache stored on disk keyed by SHA, not in Postgres, for A3 | Architecture | Rafique/Ruhan at P2-S02/P1-S05 |
| AS5 | Lab has its own Compose file and Postgres, separate from the app's | P1-S01 | Rafique |
| AS6 | Mistral's endpoint is OpenAI-compatible enough for the `openai` SDK | P1-S05 | Smoke test |
| AS7 | BM25 via `rank-bm25` (vs Postgres FTS) | P2-S03 | Rafique at P2-S03 |
| AS8 | Docker socket proxy image `tecnativa/docker-socket-proxy` | P2-S01 | Rafique at P2-S01 |
| AS9 | GitHub issues for intake live in a separate public repo `traceforge-lab-issues` or labelled issues on the main repo | P2-S06 | Ruhan |
| AS10 | A3 reviewer identity is a free-text name (no login) | P2-S05 | Both |

## Open questions
| # | Question | Affects | Owner | Blocking? |
|---|---|---|---|---|
| Q1 | Exact Devstral model ID and Mistral free-tier limits (RPS, tokens/month, data-training terms) | P1-S05, P4-S01, P5-S03 | Ruhan | Blocks experiments |
| Q2 | Official Devstral list price for the business section (only Mistral Large $0.50/$1.50 per 1M was found on the official page) | P0-S04 | Ruhan | No |
| Q3 | Does the supervisor approve the revised 2-member scope and R&D track in writing? | P0-S04, submission | Ruhan | Blocks submission |
| Q4 | Ruhan's GitHub username, to add as collaborator | P0-S01 | Rafique | Blocks Ruhan's pushes only (merges no longer need his approval) |
| Q5 | ~~Synverk flows~~ Resolved by D16: Synverk not used | — | — | No |
| Q6 | Latency targets per case (none until measured) | NFR-03 | Both | No |
| Q7 | A4 public host (free tier) and whether login is needed | P6-S02 | Ruhan | No (A4) |
| Q8 | A4 deadline and A3 demo date: user said dates don't matter; sequencing is by dependency only | Roadmap | — | No |
| Q9 | Ruhan's GPU model (Rafique's is RTX 3050 6 GB; Ruhan's reported as 6 GB) | P5-S04 hardware note | Ruhan | No |

## Contradictions found
| # | Where | Contradiction | Resolution |
|---|---|---|---|
| X1 | Proposal PDF vs current decisions | PDF lists 3 members, GPT-4.1-mini primary, RTX 4050 | P0-S04 updates the proposal; current decisions win |
| X2 | Audited architecture §14 vs repo rules | Layered `api/`, `db/` folders vs feature folders required by `docs/invariants/core.md` | Repo rules win; [ARCHITECTURE.md](ARCHITECTURE.md) uses feature folders |
| X3 | `main` vs PR #1 | `main` has the plan without the five safeguards; PR #1 adds them | Resolved: PR #1 and #2 merged 19 Nov 2026 |
| X4 | TRAC-10 (agent) waits on TRAC-8 (incidents API) | The agent CLI runs on samples and doesn't technically need the incidents API | Kept as on the card (card wins); this plan lists the same dependency. Can be relaxed on the board if Ruhan wants to start the agent earlier |
| X5 | TRAC-23 (A3 delivery) doesn't wait on TRAC-17 (GitHub intake) | The demo needs the real integration (rubric C4) | This plan makes P4-S03 depend on P2-S06; suggest adding TRAC-17 to TRAC-23's waits on the board (not changed here) |
| X6 | TRAC-23 is one card but covers three activities | Experiments, failure analysis, demo pack have different owners | Split into P4-S01/S02/S03 here; all map to TRAC-23 |
| X7 | AGENTS.md says `instructions.md`; the file is `INSTRUCTIONS.md` and marked superseded (history only) | Request named `instructions.md` | Read `INSTRUCTIONS.md`; its still-valid rules live in `docs/invariants/` |
| X8 | Cards name owners in titles but have no Synverk assignee | Ruhan isn't a project member | Moot (D16): owners live in the step documents |
| X9 | `INSTRUCTIONS.md` §5b says ORM only; its header says raw sqlite3 for another project | Different project | SQLAlchemy chosen (D14) |
