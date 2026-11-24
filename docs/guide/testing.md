# Testing

> **Status sync 2026-11-25 (final).** This chapter was written on 2026-11-21 and parts are historical. Current status of Ruhan's 20 primary tasks: **none COMPLETE & VERIFIED**; 10 IMPLEMENTED NOT VERIFIED, 10 PARTIALLY COMPLETE, 0 NOT STARTED. Nothing is reviewed by Rafique or approved by the owner. Authoritative: `docs/plans/RUHAN_TASK_TRACKER.md`. Where this chapter says Rafique's components are absent, there is no experiment, or the model is undecided, that is stale: the lab, sandbox, evidence, graph, retrieval, metrics and a 184-case frozen dataset exist; a reduced RC1 evaluation exists in `results/final` (35 sites at replicate 0, 12 at replicate 1, 8 at replicate 2; AxForge `glm-5.3-flash`) and is adopted as the A3 final evaluation for diagnosis/repair with the shortfall disclosed (Q19 decided 2026-11-25); the team is two members (Rafique, Ruhan).


Back to [TraceForge Explained](TraceForge-Explained.md). Plan source: `docs/plans/TESTING_AND_VALIDATION.md`. Numbers source: `docs/orchestration/STATE.md` (updated 2026-11-21). **No count in this chapter was produced by me**; I did not run the suites while writing. Re-run `task test` and `task web:test` for current numbers.

## 1. Verified numbers (from `docs/orchestration/STATE.md`)

| What | Result | Date | Notes |
|---|---|---|---|
| Backend baseline re-run | `uv run pytest` = **24 passed, 1 skipped**; ruff clean | 2026-11-21 | Skip is `tests/test_health.py:22`, the DB-up test, because Postgres was not running. This was *before* the new work |
| Full backend suite after P0-S03, P1-S04, P1-S05 | **229 passed, 1 skipped**; ruff clean | 2026-11-21 (stated in STATE.md "Done this session") | |
| Full backend suite after all Track B work so far (Postgres 16 up, migrations 0001+0002) | **360 passed, 0 skipped**; `ruff check` and `ruff format --check` clean; frontend 24 tests passed + build OK | 2026-11-21, end of session 1 (run by the orchestrator) | |
| Frontend | **5 tests pass** | 2026-11-21 | `HealthBadge.test.tsx` |

Not in STATE.md, so **not stated here as verified**: a pass count after the pipeline (`agent/pipeline.py`) and repair (`repair/`) tests were added; whether `task lint` passes now; whether `pnpm build` passes now. Earlier numbers in `docs/plans/RUHAN_CHECKLIST.md` (189 incident tests on SQLite incl. all 169 state pairs; 16 mocked gateway tests) are the checklist's own claims at its writing time. The 169 figure is 13 x 13 state pairs.

## 2. What each test group proves

| Group | File(s) | Proves |
|---|---|---|
| Contract samples | `tests/test_contract_samples.py` | All 3 samples per contract load and round-trip; bad data (missing target, over budget, Windows path, uncited diagnosis) is rejected |
| Health | `tests/test_health.py` | `ok/up` when DB reachable; `degraded/down` (not a crash) when not |
| Incident state machine | `tests/incidents/test_incidents_service.py` | Every state pair behaves as the map says; guards reject and write nothing; audit rows carry actor, payload, hash; repository offers no update/delete |
| Incident API | `tests/incidents/test_incidents_api.py` | 201, 404, 422, pagination, 409 on illegal move |
| Postgres concurrency | `tests/incidents/test_postgres.py` | Only one of several concurrent transitions wins; **skipped unless Postgres is running** |
| Gateway | `tests/agent/test_gateway.py` | Cache hit/miss, retries, error handling, pricing, free-only guard, log hygiene, JSON-text tool calls |
| Pipeline | `tests/agent/test_pipeline.py` | Diagnose/patch behaviour on sample cases with a **fake model** (`FakeChat`), injection test, no hidden test text in prompts, budgets, state progress |
| Repair policy and loop | `tests/repair/` | Policy reasons; loop on a toy git repo with a **fake test runner**: correct patch verified, wrong patch rejected by hidden suite, F0/F1 get equal attempts, hidden suite once and never leaked |
| Frontend | `frontend/src/health/HealthBadge.test.tsx` | 5 UI states |

## 3. Real (non-mocked) model evidence

Two files from the local smoke run exist in the working tree:
- `backend/runs/llm_calls.jsonl` (8 lines, all read): every line is provider `ollama`, model `qwen2.5-coder:7b`, same request key, 164 tokens in, 18 out. Two lines are live calls (`cache_hit: false`): the first took about 269,953 ms (about 4.5 minutes; likely a cold model load, cause not recorded), the second about 3,625 ms. The other 6 lines are cache hits with latency 0.
- `backend/.cache/llm/ollama/qwen2.5-coder_7b/85/8579bf...json`: the cached response.

This shows the gateway reached a real local model and the cache works. It is not a quality measurement.

## 4. Things not tested or not verified (pending)

- Alembic migration `0001_incidents.py` on real PostgreSQL (header says not applied).
- Row locking and JSONB on Postgres, except via the skipped test.
- Live proxy from frontend to a running backend, and screenshots (RUHAN_CHECKLIST P0-S03).
- The pipeline on real evidence, real retrieval or a real sandbox (none exist yet).
- Any model-quality number for diagnosis or repair; any retrieval metric on a frozen dataset; any L0/G0/L1/G1 comparison. All **pending** (Phases 3-5).
- Model probe (P0-S06 Part B): not run.
- Smoke on Mistral (not usable, see [problem log](problem-log.md)).
- Unknown `case_id` returning 422 on `POST /incidents`: noted as not done in the checklist.

## 5. Planned testing (from the plan, not built)

Integration tests under `tests/integration/` (`test_sync1`, `test_pipeline_e2e` from cached LLM responses, `test_no_hidden_leak`), security tests for the sandbox, evaluation metrics tests, AI evaluation with Recall@5, MRR, nDCG@10, cause-class accuracy, abstention precision and verified repair rate on a held-out test split of at least 50 labelled examples per AI component. Commands `task lab:test`, `task sandbox:selftest`, `task dataset:validate`, `task eval:*` are listed in the plan and **do not exist** in `Taskfile.yml`.

## 6. Quality gates (`docs/orchestration/QUALITY_GATES.md`)
A task closes only when its gates pass: acceptance criteria mapped to tests, feature folders and files under 300 lines, no placeholders, `ruff check` and `ruff format --check` pass, counts come from real runs, no secrets in logs, hidden tests never in prompts, docs updated, research validity (four conditions, 3 attempts, temperature 0, pinned model, negatives kept), and no commits without approval.

## 7. Verified numbers, 2026-11-25 (supersede section 1)
Backend full CI-style run 1022 passed, 4 skipped, 36 deselected (one failure fixed afterwards, then CI green; earlier 983 passed / 21 skipped was before the 25 Nov changes). Targeted on 25 Nov: `tests/integration` 7 (Sync 1, fake gateway); reports 13; incidents 196; reviews 20; repair 64; `tests/agent` 339+3 (RC2, hw_monitor); `tests/regression` 26. Frontend vitest 12 files / 78 tests; `tsc -b` clean; `vite build` ok; ruff check/format clean. CI run on `64073ca` green on all four jobs (backend, contracts, frontend, docker). Docker: both images build; compose up healthy locally. Real HTTP end-to-end with local Ollama reached DIAGNOSED and approve/reject CLOSED (`docs/demo/e2e-run.md`). NOT done: PATCH_PROPOSED/VERIFIED through the real path on a strong provider (owner-gated), a clean-clone dry run. The pass counts in section 1 are 21 Nov history; the "not tested" list in section 4 is mostly stale except the model-quality caveats (see `docs/research/final-evaluation-report.md`).
