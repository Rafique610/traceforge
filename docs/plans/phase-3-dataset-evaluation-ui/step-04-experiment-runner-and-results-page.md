# P3-S04 — Experiment runner and results page

## A. Task identification
| Field | Value |
|---|---|
| Phase | 3 Dataset, evaluation and UI |
| Step | 4 |
| Task ID | P3-S04 |
| Synverk card | TRAC-22 (screenshot required) |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | — |
| Reviewer | Muhammad Rafique |
| Priority | Normal |
| Effort | 2.5 days |
| Status | NOT STARTED |
| Branch | `ruhan/P3-S04-experiment-runner` |

## B. Objective
Run the pipeline over a whole manifest under one fixed condition, reproducibly and within free-tier limits, and show the computed results in the app. Without this, the A3 and A4 experiments can't be run or presented.

## C. Prerequisites
- P2-S04 (repair loop), P2-S07 (real pipeline), P1-S05 (cache, rate limiter), P3-S02 (report shape; build against sample report JSON first), P3-S01 (freeze, for test-split runs).

## D. Technical background
- **Condition files** (`evaluation/conditions/{L0,G0,L1,G1}.yaml`): model profile and exact model ID, temperature 0, diagnose step budget, token budget, attempts = 3, feedback on/off, retrieval mode L/G, prompt versions. The condition file's hash goes into every record.
- **Run directory:** `runs/<split>/<condition>/<run_id>/` with one record per case + `meta.json` (dataset SHA, git SHA, condition hash, start/end, provider limits). Git-ignored (assumption AS3); results that go into slides are exported separately.
- **Resume:** skip cases already recorded in the run dir.
- **Freeze guard:** `SPLIT=test` requires `sha256(test.jsonl + hidden tests) == test.sha256`, else abort.
- **Throughput:** obey `llm_max_rps`; lab apply/restore per case is the slow part, so cases run sequentially in A3 (parallelism is a P5-S03 concern).

## E. Implementation instructions
1. `evaluation/runner.py`: `run(split, condition, run_id=None, limit=None)`; loads manifests, enforces the freeze guard, iterates cases (apply → incident → pipeline → record → restore), writes records and `meta.json`, prints progress and ETA.
2. `evaluation/conditions/*.yaml` + loader with schema validation.
3. `task eval:run SPLIT=dev CONDITION=L0 [LIMIT=10] [RUN_ID=...]`.
4. Endpoints (Ruhan's lane): `GET /evaluation/runs` (list run dirs with meta), `GET /evaluation/report?runs=<ids>` (calls Rafique's `build_report`).
5. `frontend/src/evaluation/ResultsPage.tsx`: choose runs; tables for retrieval (E1 JSON too), diagnosis (LLM vs RULES), repair (L0 vs G0), system (latency median/P95, cost); breakdown toggles (class, family, distance); every number shows its `n`.
6. Tests: freeze guard rejects a modified manifest; resume skips done cases; condition validation; results page renders the sample report.

Edge cases: provider outage mid-run → stop cleanly, resume later; a case crashing the pipeline → record `UNVERIFIED` with the error, continue.

## F. Checklist
- [ ] Condition files and loader
- [ ] Runner with resume and freeze guard
- [ ] Run directory layout with meta
- [ ] CLI task
- [ ] Runs list and report endpoints
- [ ] Results page with breakdowns and n
- [ ] Tests (guard, resume, conditions, page)
- [ ] Dev-split run completed and resumed after a manual interrupt
- [ ] Screenshot on TRAC-22

## G. Expected deliverables
New: `backend/traceforge/evaluation/{runner.py,conditions/*.yaml}`, evaluation router, `frontend/src/evaluation/*`, tests. Modified: `Taskfile.yml`, `README.md`.

## H. Testing and validation
- Interrupt a dev run with Ctrl+C, rerun with the same `RUN_ID` → continues where it stopped; second full rerun is served from cache.
- Acceptance: the results page numbers equal `task eval:report` output for the same runs.

## I. Dependencies and integration
- **Depends on:** P2-S04, P2-S07, P3-S02 (report), P3-S01 (for test split).
- **Unblocks:** P4-S01, P5-S03, P5-S04.

## J. Definition of done
Merged after Rafique's review; resumable dev run; results page matches CLI report; screenshot attached; TRAC-22 approved.
