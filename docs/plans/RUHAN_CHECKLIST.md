# Ruhan's live checklist (Track B)

Source of truth for ownership: [TEAM_WORK_DISTRIBUTION.md](TEAM_WORK_DISTRIBUTION.md) §2.2/§3 (read 21 Nov 2026, `main` @ 839a62d). Task IDs and step paths are the repo's own. Status vocabulary: NOT STARTED, PARTIALLY COMPLETE, IMPLEMENTED NOT VERIFIED, BLOCKED, COMPLETE & VERIFIED. A box is ticked only with evidence. Per AGENTS.md, only the project owner approves a step; I set NEEDS REVIEW.

**Status sync 2026-11-25 (authoritative detail: `RUHAN_TASK_TRACKER.md`).** Five facts per task: Implemented / Tested / Integrated / Reviewed / Approved, plus one label. Nothing is Reviewed (Rafique's review is outstanding) or Approved (no owner approval recorded), so **0 / 20 COMPLETE & VERIFIED**. Boxes below stay unticked on purpose: a box means approved, not merely implemented. The per-task notes further down are dated history (21 to 23 Nov); where they disagree with this section or the tracker, this section wins (e.g. repair tests are 64, not 24 or 28; vitest is 78, not 65; P1-S07 is no longer blocked on P1-S03, which is complete, and `tests/integration/test_sync1.py` exists).

Ruhan has exactly **20** primary steps (P0-S03, P0-S04, P1-S04..S07, P2-S04..S06, P3-S03, P3-S04, P4-S01, P4-S03, P5-S03, P5-S04, P5-S10, P5-S11, P5-S17, P6-S02, P6-S03). Supporting only, not counted: P0-S05, P0-S06 Part B, P6-S04, P5-S16 label verification. The earlier "0 / 23" and "0 / 22" figures were wrong.

| Phase | Ruhan primary steps | Labels (2026-11-25) | COMPLETE & VERIFIED |
|---|---|---|---|
| 0 | S03, S04 (supporting: S05, S06-B) | S03 IMPLEMENTED NOT VERIFIED; S04 PARTIALLY COMPLETE | 0/2 |
| 1 | S04, S05, S06, S07 | S04, S06, S07 IMPLEMENTED NOT VERIFIED; S05 PARTIALLY COMPLETE | 0/4 |
| 2 | S04, S05, S06 | all IMPLEMENTED NOT VERIFIED | 0/3 |
| 3 | S03, S04 | both IMPLEMENTED NOT VERIFIED | 0/2 |
| 4 | S01, S03 | both PARTIALLY COMPLETE (Q19 DECIDED: reduced RC1 evaluation adopted, shortfall disclosed; no dry run) | 0/2 |
| 5 | S03, S04, S10, S11, S17 | all PARTIALLY COMPLETE: S03 (decision made, shortfall disclosed); S04 (local comparison done, n=12); S10 (opt-in, benefit UNPROVEN); S11 and S17 (regression layer implemented and tested, NOT integrated) | 0/5 |
| 6 | S02, S03 (supporting: S04) | S02 PARTIALLY COMPLETE (CI green on 64073ca; no host); S03 IMPLEMENTED NOT VERIFIED | 0/2 |

Totals by label (final sync 2026-11-25): 10 IMPLEMENTED NOT VERIFIED, 10 PARTIALLY COMPLETE, 0 NOT STARTED, 0 COMPLETE & VERIFIED. P5-S10, P5-S11 and P5-S17 moved to PARTIALLY COMPLETE (see the tracker for the evidence); P4-S01 and P5-S03 are PARTIALLY COMPLETE with Q19 DECIDED (reduced RC1 evaluation adopted, shortfall disclosed); P5-S04 local comparison done; P6-S02 CI green on 64073ca. Human-only items are NOT done: written confirmation of the revised proposal by the supervisor (the 18 Nov email is conditional permission to proceed only), Rafique review, owner approval, public URL, hosting, branch protection. The owner-gated blocker for the real patch path is one AxForge investigation (`--axforge-billing-verified`; see the tracker).

Columns per task: Dependencies · Files · Acceptance · Tests · Evidence · Commits · Blockers · Next action. Evidence/commits are empty until work happens.

## Phase 0 — Foundation
- [ ] **P0-S03** Frontend scaffold (TRAC-2) — 1 d. **NEEDS REVIEW** 2026-11-21: `pnpm test` 5/5, `pnpm build`, lint pass. UNVERIFIED: live proxy 200 against running backend, screenshots. Files: `frontend/**`, Taskfile web tasks, README.
  - Deps: P0-S01 (my clone closes it), P0-S02 (done). Files: `frontend/**`, `Taskfile.yml`, `README.md`.
  - Acceptance: HealthBadge shows 4 states from the real response; no hardcoded "ok". Tests: Vitest for 4 states; `task web:test`.
  - [ ] Implementation [ ] Unit tests [ ] Docs (README) [ ] Acceptance (screenshots)
  - Next: needs Node + pnpm (pnpm **not installed**; `corepack enable`).
- [ ] **P0-S04** Proposal update + supervisor approval (TRAC-3) — 1 d. Not started.
  - Deps: none technical; Rafique reviews technical sections. Deliverable: revised PDF (kept outside repo), email, saved reply. Update 2026-11-25: the 18 Nov supervisor email (conditional written permission to proceed; Q3 ANSWERED-CONDITIONAL) is saved at `D:\TraceForge\Assignment_3_TraceForge\Evidence\`; revised PDF dated 23 Nov exists; written confirmation of the revised version is still external.
  - Source proposal PDF is **not in the repo** (gitignored) — I need it.
- [ ] **P0-S05** Contracts — supporting. **Confirmation proposed 2026-11-21** (additive, in working tree): `AgentRunRecord.provider` free-form slug (was mistral/ollama/groq); new optional `replicate`, `temperature`, `seed`, `failure_reason`; schema regenerated. Sample tests rerun in full suite (229 pass). Needs Rafique heads-up (shared contract).
  - Files: `backend/traceforge/contracts/**`. Acceptance: all samples validate, round-trip. Tests: `backend/tests/test_contract_samples.py`.
  - Next: review the 5 contracts vs INTEGRATION_PLAN field list (agent-side fields: `AgentRunRecord`, `ContextBundle`, `EvidenceBundle`); report disagreements as a contract PR.
- [ ] **P0-S06 Part B** Model probe — branch `ruhan/P0-S06-model-probe`, 2 d. Not started.
  - Deps: P0-S02. Needs Mistral API key (free) in `.env`, Ollama `qwen2.5-coder:7b`, ripgrep (not installed).
  - Output: `spikes/model_probe/`, `results/*.json`, fill Part B of `docs/research/limits-report.md` (exists on branch `origin/rafique/P0-S06-retrieval-spike`, not yet on main); settle D19/D20/D21.
  - Acceptance: read-limit (100/300/1k/3k/6k lines ×3), write-limit (5/20/50/100 lines), diff vs search/replace on 10 fixes, per-edit quality, real free-tier limits, both models.
- [ ] Review every Track A PR within one working day (standing duty).

## Phase 1 — Core components
- [ ] **P1-S04** Incidents API + DB (TRAC-8) 2 d. **NEEDS REVIEW** 2026-11-21: 189 tests (SQLite; all 169 state pairs), ruff clean. Postgres VERIFIED 2026-11-21 (docker postgres:16): migration up/down/up OK; `tests/incidents/test_postgres.py` (8 concurrent transitions → exactly 1 wins, JSONB round trip) passes; health DB-up test passes. Unknown-`case_id` 422 DONE 2026-11-22 (when a dataset manifest is configured; no check otherwise, since the dataset is not frozen). Deps P0-S02, P0-S05. Files `backend/traceforge/incidents/**`, Alembic migration. Acceptance: VERIFIED without red/green payload → 409, nothing written. Tests: all transition pairs, guards, audit append-only.
- [ ] **P1-S05** Model gateway + cache + ADR 0001 (TRAC-9) 2 d. **Implemented, partly verified** 2026-11-21: 16 mocked tests pass. Live smoke on local Ollama qwen2.5-coder:7b PASSED 2026-11-21 (live call then cache hit) after adding `tool_calls_from_text` adapter (model prints tool calls as JSON text). NOT DONE: `gateway:probe`, ADR 0001 (needs probe numbers), cloud-provider smoke (no key yet). Provider-agnostic + free-only guard (DECISIONS B4). Deps P0-S02 (informed by P0-S06). Files `agent/{gateway,cache,call_log,smoke}.py`, `docs/adrs/0001-primary-model.md`. Acceptance: smoke on Mistral + Ollama, 2nd run cache hit; Q1 closed. Includes `task gateway:probe`; cache key = prompt+model+replicate (D26).
- [ ] **P1-S06** Pipeline agent (TRAC-10) 3 d. **Implemented 2026-11-21**: 33 agent tests pass with fake gateway (config/code/abstain/runtime_dependency, injection, malformed output, hidden-leak, budget). NOT verified: live model run of `agent:run`, D20 budget (placeholder 12000 chars). Deps P1-S04, P1-S05, P0-S05. Acceptance: injection test passes; abstain/runtime_dependency → no patch; D20 context budget; code-map tool in both arms.
- [ ] **P1-S07** Sync 1 (TRAC-11, primary) 0.5 d. Deps P1-S03 (Rafique, complete), P1-S06. Acceptance: 4 schema-valid records; offline integration test. 2026-11-25: `tests/integration/test_sync1.py` 7 passed (fake gateway); IMPLEMENTED NOT VERIFIED.

## Phase 2
- [ ] **P2-S04** Repair loop (TRAC-15) 3.5 d. **Core implemented 2026-11-21**: `repair/` 24 tests pass (policy, worktree, F0/F1 equal attempts, no-leak, correct patch verified vs wrong rejected on real temp git repo + real pytest). NOT done: patches/validation_runs tables (moving to P2-S05 migration 0002), CLI, real sandbox (Rafique P1-S02), pipeline wiring. Deps P1-S06, P1-S02 (Rafique; fake runner until then), P1-S03. Acceptance: no-leak + equal-attempts tests; hand-correct patch verified, hand-wrong rejected; ≤60 lines/≤2 files/no tests; test-literal check.
- [ ] **P2-S05** Report + review (TRAC-16) 1.5 d. Deps P1-S04, P2-S04. Acceptance: no LLM-generated report field; tamper hash → 409.
- [ ] **P2-S06** GitHub intake (TRAC-17) 1.5 d. Deps P1-S04. Acceptance: real issue URL → incident with untrusted evidence; offline → clear error. Open AS9 (issues repo).

## Phase 3
- [ ] **P3-S03** Reviewer UI (TRAC-21) 4 d. Deps P0-S03, P2-S05 (can start on samples).
- [ ] **P3-S04** Experiment runner + results page (TRAC-22) 2.5 d. Deps P2-S04, P2-S07, P3-S02, P3-S01. Acceptance: resumable run; page == `task eval:report`.

## Phase 4
- [ ] **P4-S01** A3 experiments (E1, L0 vs G0, baseline) 2 d. Deps P2-S07, P3-S01, P3-S02, P3-S04.
- [ ] **P4-S03** Demo + submission pack 1.5 d. Deps P0-S04, P2-S06, P3-S03, P4-S02.

## Phase 5
- [ ] **P5-S03** Full 2×2 × 3 replicates 3 d (+ unattended). Deps P4-S03, P3-S04.
- [ ] **P5-S04** Model sensitivity (local Qwen) 2 d. Deps P5-S03 (G1).
- [ ] **P5-S10** RC2 pipeline robustness fixes (added 2026-11-24) 2 d. Deps none for design; owner approval to start. Parallel with P5-S06..S08. Reviewer Rafique.
- [ ] **P5-S11** Conditional end-to-end hybrid experiment (added 2026-11-24) 2 d + unattended. Deps P5-S08 go (+P5-S10). Needs owner approval for AxForge spend; Rafique supports retrieval wiring.
- [ ] **P5-S17** Regression-aware repair validation (added 2026-11-25, PROPOSED, CONDITIONAL) 3 d. Deps owner approval, P5-S10 (RC2), P5-S15 and P5-S16 showing benefit. RC2 only, new fingerprint, never RC1. Rafique supports (impact/selection interface), reviewer Rafique. NOT STARTED. Separately, Ruhan independently verifies P5-S16 hand-labelled expected relationships (supporting, not counted).

## Phase 6
- [ ] **P6-S02** CI + deployment 3 d. Deps P4-S03. Open Q7 (host).
- [ ] **P6-S03** UI polish + audit view 2.5 d. Deps P3-S03, P5-S02.
- [ ] **P6-S04** Paper/pitch — supporting (agent/system sections, pitch). Deps P5-S02, P5-S03.

## Ambiguities / flags
1. Distribution lists Ruhan's steps as 20 items incl. the review duty and P0-S05/P6-S04 support; roadmap lists P6-S04 owner as Rafique (+Ruhan). Treated as supporting.
2. AGENTS.md says `INSTRUCTIONS.md`/`CLAUDE.md` are history/absent; neither exists in the repo (INSTRUCTIONS.md is gitignored).
3. The user prompt's eleven concerns and "boundary prototype" map onto P0-S06; they are not step IDs in the repo. Research experiments for them have no assigned step yet — needs a decision on where they live (see report).

## Status log — latest verified state (2026-11-21, end of session 1)
Verification run today: backend `pytest` **360 passed, 0 skipped** (Postgres 16 up, migrations 0001+0002 applied, `alembic check` clean), `ruff check` + `ruff format --check` clean; frontend `pnpm test` 24 passed, `pnpm build` OK. Nothing committed. **No task is "Verified complete"** — Ruhan approves steps (AGENTS.md).

| Task | State | Evidence / what is missing |
|---|---|---|
| P0-S03 | NEEDS REVIEW | tests/build/lint pass; missing: screenshots, live proxy 200 |
| P0-S04 | DRAFTED, blocked (external) | `phase-0-foundation/step-04-proposal-update-draft.md`; (21 Nov log; since then the 18 Nov supervisor email is on disk as conditional permission, Q3 ANSWERED-CONDITIONAL) needs Rafique review and written confirmation of the revised proposal |
| P0-S05 | Confirmation proposed | additive `AgentRunRecord` fields + free-form `provider`; Rafique not yet told |
| P0-S06-B | Implemented, partly run | local qwen2.5-coder:7b read/write/format/latency numbers in `docs/research/limits-report.md`; a Nemotron `:free` format test (experimental alternative only; NOT Devstral). **Devstral runs NOT RUN** (no free access found; see DECISIONS B11). NOT RUN: 3k/6k-line read, cloud read/write, free-tier daily limit. D19 supported on Qwen (and on Nemotron); D20 local-only; D21 undecided (Devstral untested) |
| P1-S04 | NEEDS REVIEW | Postgres verified (migration up/down, 8-way concurrent transition, JSONB). Missing: unknown-`case_id` 422 |
| P1-S05 | Implemented, partly verified | 17 gateway tests; live smoke passed on Ollama and OpenRouter `:free`; free-only guard verified. `gateway:probe` task added 2026-11-22; ADR 0001 updated (still PROPOSED, no probe numbers for AxForge) |
| P1-S06 | Implemented | 34+ agent tests with fake gateway; no live end-to-end `agent:run` yet; D20 budget placeholder |
| P1-S07 | (21 Nov, stale) BLOCKED | superseded: P1-S03 is complete and test_sync1 exists (25 Nov) |
| P2-S04 | Core + wiring implemented | repair loop + `run_case_with_repair`, F0/F1, hidden isolation tests; uses fake/real-pytest runner, NOT Rafique's sandbox; no CLI; D31 literal check can reject legitimate patches (e.g. literal 100) — limitation to report |
| P2-S05 | Implemented, SQLite+Postgres migration | 26 tests; REVIEWED→CLOSED automatically; payload keys (`evidence_ids`, `missing_evidence`, patches.impact) must be written by the pipeline — not yet |
| P2-S06 | Implemented | 39 mocked tests; live demo NOT RUN (needs an allowlisted public issue) |
| P3-S03 | NEEDS REVIEW | 24 UI tests; no real-backend walkthrough/screenshots; investigate endpoint pending (P2-S07) |
| P3-S04 | Backend half implemented | 6 tests; results page and `GET /evaluation/report` not built; conditions JSON still name devstral/mistral — repoint after model decision |
| P4-S01, P4-S03 | BLOCKED | need frozen dataset (P3-S01), metrics (P3-S02), Rafique pipeline pieces, supervisor reply |
| P5-S03, P5-S04 | BLOCKED | need P4 and real dataset |
| P6-S02 | Files authored | CI workflow, two-stage Dockerfiles, `compose.prod.yaml`, showcase middleware (6 tests), ADR 0002 draft. NOT RUN: image builds, CI, deployment |
| P6-S03 | Not started | needs P3-S03 live + P5-S02 stats |
| P6-S04 | Not started (supporting) | needs P5 results |

### Update — later 2026-11-21 (see `docs/plans/RUHAN_AUDIT.md` addendum for evidence)
- P0-S03: screenshots (ok/degraded/unreachable) + real-backend walkthrough DONE → ready for Ruhan's review.
- P2-S06: live intake on a real public issue DONE (pallets/flask#6190) → ready for review.
- P6-S02: both Docker images built and smoke-tested (API 334 MB non-root, web 74 MB, proxy works). NOT RUN: CI on GitHub, compose.prod stack, deployment.
- P3-S04: results page built (raw counts only); computed metrics wait for Rafique (P3-S02).
- P2-S04: D31 test-literal false positive fixed (rule documented, 0/14 wrong on its table).
- P1-S05: ADR 0001 written as PROPOSED; gateway guard for Ollama `-cloud` models added; output cap now a setting.
- Real-model sample runs (not Devstral; sample sources; no sandbox) recorded in the audit addendum.
- Contacts/materials for blocked items: `docs/plans/UNBLOCK_MESSAGES.md`.
