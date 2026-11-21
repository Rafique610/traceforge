# Ruhan's review package (P0-S03, P1-S04, P2-S06) — 2026-11-21

Rule (AGENTS.md): only Ruhan approves a step. Nothing here is approved yet. Do these one at a time; tell Claude what you saw and whether to approve, change or reject. You do not need to read source code: each review says what to click and what to expect.

Services for all three reviews (Claude starts them for you; commands are listed if you want to do it yourself):
```powershell
cd D:\TraceForge\repo
docker compose up -d --wait db                 # Postgres (port 5433)
cd backend; $env:PYTHONUTF8=1
..\backend\.venv\Scripts\python.exe -m uvicorn traceforge.main:app --port 8000   # API  (needs .env loaded; Claude uses a helper script)
cd ..\frontend; pnpm dev --port 5173           # UI
```
Open: UI http://localhost:5173 , API docs http://localhost:8000/docs

---
## Review 1 — P0-S03 Frontend scaffold
1. **What it does:** the web app shell. A header with a live "API ok / degraded / unreachable" badge and the pages that later reviews use.
2. **Why TraceForge needs it:** reviewers (humans) must see the evidence and decide without a terminal; the badge proves the browser really reaches the API.
3. **What was implemented:** Vite + React + TypeScript app; `/api` proxy to the backend; `HealthBadge` with 4 states computed from the real `/health` response; tests.
4. **Files:** `frontend/src/shared/api.ts` (calls the API), `frontend/src/health/HealthBadge.tsx` (the badge), `frontend/src/App.tsx` (page shell), `frontend/vite.config.ts` (proxy), `frontend/src/health/HealthBadge.test.tsx` (tests).
5. **Tests run (2026-11-21):** frontend 29 tests passed, production build OK.
6. **Evidence:** screenshots `docs/screenshots/badge-ok.png`, `badge-degraded.png`, `badge-unreachable.png`, `ui-list.png`.
7. **How to test (manual):** open http://localhost:5173 → badge top-right says **API ok** (green). Stop the database (`docker compose stop db`), reload → **API degraded**. Stop the API (Ctrl+C in its window), reload → **API unreachable** (red) and the list shows an error with Retry. Restart both.
8. **Expected:** the three states appear exactly as above; nothing on screen is invented (text comes from the API response).
9. **Limitations:** no login; styling is plain; the "Investigate" button is disabled (needs the investigate endpoint, step P2-S07).
Approve? ☐ approve ☐ changes needed: ________

## Review 2 — P1-S04 Incidents API
1. **What it does:** stores each incident (a failing service report), moves it through guarded states (CREATED → … → REVIEW_PENDING → REVIEWED → CLOSED) and keeps an append-only audit trail.
2. **Why needed:** the system must refuse to claim things it has not proven (no "diagnosed" without evidence, no "verified" without a failing-then-passing test) and keep an unchangeable history.
3. **Implemented:** database tables (migration `0001`), state machine with guards, row locking, endpoints `POST /incidents`, `GET /incidents`, `GET /incidents/{id}`, `/events`, `/evidence`.
4. **Files:** `backend/traceforge/incidents/` — `states.py` (allowed moves), `service.py` (`transition()` + guards), `models.py` (tables), `router.py` (endpoints), `repository.py` (DB access); `backend/alembic/versions/0001_incidents.py`; tests in `backend/tests/incidents/`.
5. **Tests:** incidents suite incl. all 169 state pairs; **real Postgres**: migration up/down/up OK; 8 concurrent transitions → exactly one wins (`test_postgres.py`). Whole backend suite: 369 passed on 2026-11-21 (re-run before approving).
6. **Evidence:** the real end-to-end runs created incidents in Postgres (visible in the UI list, state REVIEW_PENDING); audit events in `GET /incidents/{id}/events`.
7. **How to test:** open http://localhost:8000/docs → `GET /incidents` → Try it out → Execute: you should see real incidents (including ones created by the real pipeline runs). Click `GET /incidents/{incident_id}/events` with an id: events list starts with `created` and shows each state change with actor and payload. Try `POST /incidents` with `{"symptom":"test","service":"shop_api"}` → 201, state CREATED. An illegal move is only possible through code (no public transition endpoint), so the guards are shown by tests: run `backend\.venv\Scripts\python.exe -m pytest backend/tests/incidents -q`.
8. **Expected:** 201 on create, 422 if both `case_id` and `symptom` are missing, 404 for unknown id; events are in time order and never change.
9. **Limitations:** unknown `case_id` is not rejected with 422 yet (no manifest path in config); no authentication.
Approve? ☐ approve ☐ changes needed: ________

## Review 3 — P2-S06 GitHub issue intake
1. **What it does:** turns a public GitHub issue URL into an incident, storing the issue text as *untrusted evidence*.
2. **Why needed:** the project must work with a real external system (assignment requirement) and must treat issue text as data, never as instructions.
3. **Implemented:** strict URL parser, owner allowlist, GitHub REST client with timeouts/size cap, secret redaction, endpoint `POST /incidents/from-github`.
4. **Files:** `backend/traceforge/github/` — `client.py` (fetch), `service.py` (create incident + redact), `schemas.py` (URL rules), `router.py`; tests `backend/tests/github/` (39).
5. **Tests:** 39 mocked tests pass (URL accept/reject table, allowlist, 404/403/429/500/timeouts, redaction, injection-as-data).
6. **Evidence (real):** live demo 2026-11-21: `pallets/flask#6190` → incident `4d1a4ca6…` in real Postgres, evidence `EV-0001` "UNTRUSTED github issue …"; a disallowed owner returned 422. Visible in UI list (screenshot `docs/screenshots/ui-detail.png`).
7. **How to test:** the allowlist is empty by default, so set it first (Claude does this when starting the API for this review: `TRACEFORGE_GITHUB_ALLOWED_OWNERS=["pallets"]`). In http://localhost:8000/docs → `POST /incidents/from-github` with `{"url":"https://github.com/pallets/flask/issues/6190","service":"shop_api"}`. Then open the incident in the UI (Incidents list → newest) and expand the evidence: text starts with `UNTRUSTED github issue`. Try a PR URL or another owner → clear 422 error, and no new incident appears.
8. **Expected:** 201 with `untrusted: true`; failures create nothing.
9. **Limitations:** unauthenticated GitHub rate limit (60/h); no seed issues repo yet (AS9 open); network-off case only tested with mocks.
Approve? ☐ approve ☐ changes needed: ________

---
## Later reviews (after these three)
Full debugging/repair workflow (real pipeline on seed cases, `docs/plans/RUHAN_AUDIT.md` Addendum 2) and experiment results — see the audit; the honest summary is that the pipeline runs end to end but the local 7B model produced no verified patch yet.

---
## UI redesign (frontend) — 2026-11-21, NOT approved
Plan: `docs/review/UI_REDESIGN_PLAN.md`. Before: `docs/screenshots/ui-*.png`, `badge-*.png`. After: `docs/screenshots/after/*.png` (desktop 1440 and mobile 390, light and dark dashboard, health degraded/unreachable).

What changed: app shell (sidebar, breadcrumbs, API health badge, light/dark toggle stored in localStorage), Dashboard (`#/`, KPIs and state bars from real API counts, recent incidents, latest evaluation runs, model info from the latest run meta or a report's model_usage, otherwise an honest empty state), incident list (`#/incidents`, search on the loaded page, state filter, derived diagnosis/verification), incident detail (pipeline stepper from the audit trail, Summary / Evidence grouped by kind / Retrieved context / Model diagnosis / Proposed patch / Sandbox verification / Human review), diff viewer (unified + split, line numbers, Python/YAML highlighting, per-file +/- counts, patch SHA copy), review with a confirmation step and a "nothing is deployed automatically" notice, New incident page (`#/incidents/new`), evaluation list/detail with computed metrics from `GET /evaluation/report` when available, 404 page and error boundary. No new dependencies, no backend change.

How to review (about 10 minutes):
1. Start DB, API and `pnpm dev --port 5173` (commands at the top). Open http://localhost:5173.
2. Dashboard: the numbers must equal `GET /incidents` totals (API docs). Click "Awaiting review" and check the list is filtered to REVIEW_PENDING. Toggle the moon/sun icon: theme switches and survives reload.
3. Incidents: search a word from a symptom; open a row. Check the stepper: stages without an audit event say "Not run"; "No patch" shows the real reason from the audit event.
4. Incident detail of a REVIEW_PENDING incident: read the review summary, then try Approve with no name (blocked), then with a name (a confirmation appears; Cancel sends nothing). Do not confirm unless you really intend to record a decision.
5. Open the GitHub incident (source github): evidence "UNTRUSTED github issue ..." and all later stages "Not run".
6. Stop the DB (`docker compose stop db`) and reload: badge "API degraded". Stop the API: "API unreachable" and the list shows an error with Retry. Restart both.
7. Narrow the browser to about 390 px: the sidebar becomes a drawer (menu button), tables keep the key columns.
Known gaps: no real incident has a patch row yet, so the diff viewer was screenshot on a sample diff (`diff-viewer-sample-desktop-light.png`, not incident data); retrieval snippets are not exposed by the API (only the hit count from the audit trail is shown); there are no evaluation runs on disk, so run pages show their empty/error states only in screenshots.
Approve? ☐ approve ☐ changes needed: ________
