# Current state (update at each handoff; git status is the truth)

**Final status sync 2026-11-25 (supersedes the 21 Nov text below, which is kept as history).**
- Ruhan's 20 primary tasks: 0 COMPLETE & VERIFIED; 10 IMPLEMENTED NOT VERIFIED, 10 PARTIALLY COMPLETE, 0 NOT STARTED. Reviewed and Approved are NO for every task. Per task: `docs/plans/RUHAN_TASK_TRACKER.md`.
- Tests (25 Nov): backend CI-style run 1022 passed / 4 skipped / 36 deselected; tests/integration 7; reports 13; incidents 196; reviews 20; repair 64; tests/agent 339+3; regression 26; frontend vitest 12 files / 78; `tsc -b`, `vite build`, ruff check/format clean. Interim checkpoint pushed to origin/main (up to 64073ca); CI on 64073ca green on all four jobs. Both Docker images build; compose healthy locally.
- Done 25 Nov: investigate route verified through the real HTTP path with local Ollama (DIAGNOSED, approve/reject CLOSED; PATCH_PROPOSED/VERIFIED not reached), Investigate button, `missing_evidence` audit event, `test_sync1.py`, RC2 opt-in (20 tests; benefit UNPROVEN; fingerprint `results/rc2/rc2-fingerprint.txt`; RC1 unchanged), `agent/hw_monitor.py`, P5-S04 local comparison (12 sites), `regression/` layer (26 tests, not integrated), Q19 decided.
- Open decisions (owner): Q19 is DECIDED 2026-11-25 (reduced RC1 evaluation adopted, shortfall disclosed). Still open: ADR 0001 model; ADR 0003; RC2 use / blind validation; one AxForge investigation for the real patch path (`cd backend && .venv/Scripts/python.exe -m traceforge.agent.e2e --case shop_api-001 --condition G1 --provider axforge --axforge-billing-verified --label EXPERIMENTAL-DEMO`, about 30k tokens, slot per TRACEFORGE_AXFORGE_KEY_SLOT; `src/agent/axforge.py` blocks all requests until the owner confirms billing-free allowance). Supervisor: the 18 Nov 2026 email is conditional written permission to proceed (not sign-off of the revised proposal; evidence in `D:\TraceForge\Assignment_3_TraceForge\Evidence\`). Human-only: written confirmation of the revised proposal, Rafique review, hosting (Q7), branch protection.
- UPDATE (later 25 Nov): RESOLVED for the patch stage. After the owner delegated the decision, one AxForge demonstration (slot 2, 52,024 tokens over three runs) reached TEST_VERIFIED_IN_LAB on shop_api-001; the persisted incident's report carried patch hash, diff, impact and validation runs, a wrong-hash review was refused (409), approval with the right hash returned 201 and closed the incident. Still not exercised on a strong model: starting the run through POST /incidents/{id}/investigate (the API cannot call the billing gate by design). Details: docs/demo/e2e-run.md.
- Tokens: AxForge slot 1 remaining 152,664; combined 742,728 under the 4.8M ceiling; nothing spent on AxForge on 25 Nov.
- Branch and "no commits" notes below are from 21 Nov and may not hold.


Updated 2026-11-21 (end of session 1, final update). Branch `ruhan/stage-b-work` (from main 839a62d). **No commits, no pushes.** ~47 changed/untracked paths.

- Verified today: backend `pytest` 360 passed (Postgres 16 container `traceforge-db-1`, port 5433 via git-ignored `.env`; migrations 0001+0002 applied; `alembic check` clean); ruff clean; frontend 24 tests + build OK.
- Models: local `qwen2.5-coder:7b` (+ `qwen2.5-coder-7b-ctx16k` variant) in `D:\AI\Models\ollama`; OpenRouter key in `.env` (limit 0; user told to rotate the key that was pasted in chat — new key in place and smoke-tested).
- Per-task status: see the status log at the bottom of `docs/plans/RUHAN_CHECKLIST.md`.
- Next: (1) pin experiment model after a fuller comparison, repoint `evaluation/conditions/*.json`; (2) write pipeline payload keys the report expects; (3) ADR 0001; (4) results page + `GET /evaluation/report`; (5) live agent run; (6) screenshots + real-backend UI walkthrough; (7) Docker image builds; (8) keep encyclopedia in sync (`docs/guide/`).
- Blocked/external: (21 Nov text; supervisor email since received 18 Nov, conditional permission, Q3 ANSWERED-CONDITIONAL) proposal PDF (P0-S04); Rafique's tracks (P1-S02/S03, P2-S01..03/07, P3-S01/02) for P1-S07, real sandbox/evidence/retrieval integration and all experiments (P4–P5).
- Machine: C: ~48 GB free, D: ~180 GB free; RAM tight (16 GB) — one GPU job at a time, avoid concurrent pytest + Docker + agents. Docker Desktop is running (db container up).

## Later update (2026-11-21)
- Backend full suite: **369 passed** (Postgres up), ruff clean. Frontend: 29 tests, build OK.
- Docker: `traceforge-api:local` (334 MB) and `traceforge-web:local` (74 MB) built and smoke-tested; Docker Desktop and the `traceforge-db-1` container are running (`docker compose stop db` to free RAM).
- Live evidence added: GitHub intake demo, UI screenshots (`docs/screenshots/`), real-model sample runs (local Qwen + OpenRouter Nemotron, experimental; sample sources, no sandbox). Details: `docs/plans/RUHAN_AUDIT.md` addendum.
- Model position: Devstral stays intended (no free access found — B11/B12, ADR 0001 PROPOSED); Qwen local baseline; Nemotron experimental; Ollama `-cloud` models guarded off.
- Blockers/owners: `docs/plans/UNBLOCK_MESSAGES.md`.
- Left running by me: Docker Desktop, Ollama server. API (8000) and Vite (5173) stopped.

## Update — 2026-11-21 late
- Prerequisite Track A components (lab, sandbox, seed cases, evidence, graph, retrieval, metrics) implemented and individually verified; first REAL end-to-end run done (see RUHAN_AUDIT.md Addendum 2): local Qwen 7B 0/4 cause-class, rule baseline 2/4.
- Running: lab-observability fix + revalidation + re-collected evidence + re-run E1/E2E (agent a0e2f03…).
- Model position: Devstral retired (B15); Nemotron 3 Ultra `:free` recommended (provisional, awaiting Ruhan): partial smoke 2/3 (fell for a misleading-warning abstain case); OpenRouter free quota 50/day (7 left at last read), key re-added by Ruhan; Ollama key removed from .env again (not needed).
- Pending decisions for Ruhan: approve primary/backup model; commit strategy; Mistral console check; proposal PDF (supervisor email already received 18 Nov; see Q3).
- Not done: frozen dataset (P3-S01), P4–P6 experiments/paper, CI run on GitHub, compose.prod stack run.
- 2026-11-22 model switch (B17): agent model is AxForge `glm-5.3-flash` (free allowance only; stop on any 402/error). Qwen/Nemotron/BeatAPI results preserved; BeatAPI smoke stopped at a 429 (pacing gap, fix proposed, not applied). Suite: 577 passed + 23 new-test additions; P1-S04 unknown `case_id` → 422 when a manifest is configured.
