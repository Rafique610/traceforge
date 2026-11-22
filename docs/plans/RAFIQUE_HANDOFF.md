# Rafique handoff: what exists, what remains (audit of 2026-11-22)

Evidence: `git log` (authors `Rafique610` vs `ruhank-dev`), `main` at 45e669d, the code, and test runs on 2026-11-22. Docker was not running during this audit, so Docker-dependent checks (sandbox containers, live evidence proxy, lab stack) were NOT re-run today; their status below comes from the earlier live verification recorded in `DEPENDENCY_MAP_RAFIQUE.md` section D. Nothing here is "Verified complete": only the project owner approves a step.

## 1. Rafique's own completed work (his commits)
| Item | Evidence |
|---|---|
| P0-S01 repo setup | commits c9902a1, c7e2bce, .gitattributes; Ruhan's clone/collaborator step still open |
| P0-S02 backend scaffold | commit 4a4a4df (FastAPI app, config, health); his branch is merged to `main` |
| P0-S05 shared contracts | commits 4a4a4df, 29f8a93 (`log_format` on `CaseManifest`); samples + JSON schemas in `backend/traceforge/contracts/`. NEEDS REVIEW: Ruhan's additive `AgentRunRecord` change (aa2ac9a) |
| P0-S06 Part A retrieval spike | commit 0805e6b: `spikes/retrieval/`, `docs/research/limits-report.md` Part A |
| Plan, step docs, process rules | docs commits 19-21 Nov |

## 2. Track A components that exist but were written by the Claude-assisted session for Ruhan (commits aa2ac9a, 996f004, author `ruhank-dev`)
These are Rafique's tasks by ownership. He did NOT write them and has not reviewed them. He should review and extend them, not rebuild them.
| Task | State on `main` | Verified how (and limits) |
|---|---|---|
| P1-S01 Lab (`lab/`: shop_api, worker, compose) | implemented | earlier live stack run; a realism fix (silent failure handling) was in progress; not re-run today |
| P1-S02 Sandbox (`backend/traceforge/sandbox/`) | implemented | 7 tests pass today; 12 Docker tests skipped today (earlier: all passed in real containers); worker-service tests not runnable |
| P1-S03 Fault generator + seed cases (`datasets/`, `backend/traceforge/faultgen/`) | partial: 4 dev cases (`shop_api-001..004`), `manifests/dev.json` | 21 faultgen tests pass, 2 skipped (Docker); 4 cases validated 3x earlier; distances set by hand; far below the target of at least 144 frozen + 30 dev |
| P2-S01 Evidence collector (`evidence/`) | implemented | 46 tests pass, 21 skipped (need the docker proxy); earlier live run: 18/18 writes refused, no secret leaks. Gaps: no CLI, case 004 suppressed-logs hint not honoured, health probe timeouts |
| P2-S02 Code graph (`codeintel/`) | implemented | 26 tests pass; call-resolution precision not measured |
| P2-S03 Retrieval L and G (`retrieval/`) | implemented | 24 tests pass; E1 benchmark on real evidence is not meaningful yet (2 cases, all methods near 0) |
| P3-S02 Metrics + baseline (`evaluation/`) | implemented | 25 tests pass; run only on 10 hand-made/real records; edit-quality metrics missing |

## 3. Work of Ruhan's that overlaps and should be reused
`docker compose` lab + Taskfile targets, `docs/plans/DEPENDENCY_MAP_RAFIQUE.md`, `docs/orchestration/DECISIONS.md` (B9, B13 contract changes), the RULES baseline record type, `AgentRunRecord` new optional fields (`replicate`, `temperature`, `seed`, `failure_reason`), the pipeline/repair/report code that consumes the above.

## 4. Outstanding for Rafique, dependency-first
| # | Task | What he delivers | Reuse | Remaining | Ruhan tasks waiting | Blocks or parallel |
|---|---|---|---|---|---|---|
| 1 | Review of the Track A code above and the `AgentRunRecord` change (P0-S05) | written review/approval or change requests | all of section 2 | read, run `task` checks with Docker up, list changes | everything that touches real components (P1-S07, P2-S04 integration, P3-S04) | blocks sign-off, parallel to coding |
| 2 | P1-S03 seed cases and P3-S01 frozen dataset | at least 144 validated cases in test/dev splits, manifests, `test.sha256`, peer-checked labels | `faultgen/`, 4 dev cases, validator (3 runs, ~3 min/case) | about 140 more cases, true distances, freeze hash; I check 10 random labels | P1-S07, P3-S04, P4-S01, P5-S03, P5-S04 | **critical path, blocks** |
| 3 | P1-S01 / P1-S02 hardening | lab realism fix, worker tests, sandbox on his machine | `lab/`, `sandbox/` | re-run on his laptop, fix flaky points | P2-S04 (real runner), P1-S07 | blocks real-sandbox evidence |
| 4 | P2-S01/S02/S03 finishing | collector CLI, 004 hint, graph precision, E1 on a real dataset | existing modules, retrieval spike | E1 needs traces and a larger case set | P2-S07, P3-S04 G-arm, P4-S01 | parallel with 2 |
| 5 | P3-S02 metrics on real data | metrics over real runs, edit-quality metrics | `evaluation/` | run once records exist | P3-S04 results page, P4-S01 | parallel |
| 6 | P2-S07 Sync 2 | joint session, one command running 4 cases end to end | my consumer side is wired | lead the session | P2-S07 | after 1-4 |
| 7 | P4-S02, P5-S01, P5-S02, P5-S05 (optional), P6-S01, P6-S04 | failure analysis, deeper graph, statistics, security suite, paper | none of mine overlaps | not started, deliberately untouched | P4-S03, P6-S04 support | later |

## 5. WhatsApp message
```
Hey Rafique! Quick status so we don't duplicate anything 🙏

☑ Yours and done: repo setup, backend scaffold + shared contracts (P0-S01/S02/S05), retrieval spike + limits report part A (P0-S06A)

Already in main (written by my Claude session for me, NOT reviewed by you yet, please don't rebuild, just review + extend):
☑ lab (P1-S01), sandbox (P1-S02), evidence collector (P2-S01), code graph (P2-S02), retrieval L/G (P2-S03), metrics + baseline (P3-S02). Tests pass, but I couldn't re-run the Docker ones today.
◐ seed cases (P1-S03): only 4 dev cases exist (datasets/, manifests/dev.json), faultgen is there. We need way more.

Your list, in the order I need it:
☐ 1. Review the above + my small AgentRunRecord change (optional fields replicate/temperature/seed/failure_reason, P0-S05). Details: docs/plans/RAFIQUE_HANDOFF.md
☐ 2. P1-S03 → P3-S01: grow the seed cases and freeze the dataset (hash). This is the big one, it blocks my P1-S07, P3-S04, P4-S01, P5-S03/S04. I'll peer-check 10 labels.
☐ 3. Re-run lab + sandbox on your laptop, fix flaky bits (P1-S01/S02): my P2-S04 real-runner check waits on it
☐ 4. Finish evidence/graph/retrieval gaps (P2-S01/02/03): collector CLI, case 004 hint, E1 on the bigger set. Can run parallel with 2
☐ 5. Run metrics on real runs (P3-S02): feeds my results page (P3-S04)
☐ 6. Sync 2 session with me (P2-S07)
☐ 7. Later: P4-S02, P5-S01/S02/S05(optional), P6-S01, P6-S04. I haven't touched these.

Heads up: Docker was off when I checked, so lab/sandbox live status is from my earlier run. Shout if anything looks off 👍
```
