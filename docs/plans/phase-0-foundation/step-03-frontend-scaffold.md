# P0-S03 — Frontend scaffold

## A. Task identification
| Field | Value |
|---|---|
| Phase | 0 Foundation |
| Step | 3 |
| Task ID | P0-S03 |
| Synverk card | TRAC-2 (screenshot required) |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | — |
| Reviewer | Muhammad Rafique |
| Priority | High |
| Effort | 1 day |
| Status | IMPLEMENTED, TESTED, NOT REVIEWED/APPROVED |
| Branch | `ruhan/P0-S03-frontend-scaffold` |

**Status sync 2026-11-25.** Evidence: `pnpm vitest` 12 files / 78 tests, `tsc -b` clean, `vite build` ok, oxlint warnings only. Not verified against a live backend with a real provider. Five-fact detail: `docs/plans/RUHAN_TASK_TRACKER.md`.

## B. Objective
A minimal reviewer app that proves the browser → API path works, with the folder conventions, API helper and test setup that P3-S03 builds the real UI on.

## C. Prerequisites
- P0-S01. Node LTS and pnpm (`corepack enable`).
- `/health` from P0-S02 (develop against any server returning `{"status":"ok","db":"up","version":"x"}` until it merges).
- Read `docs/invariants/frontend.md`, `core.md` (real data only).

## D. Technical background
- Vite's dev proxy forwards `/api/*` to `http://localhost:8000`, so no CORS configuration is needed in development; production setup is decided in P6-S02.
- Feature folders under `src/`: `health/`, later `incidents/`, `review/`, `evaluation/`; shared helpers in `src/shared/`.
- Real data only: the badge must reflect the actual response; no hardcoded "ok".

## E. Implementation instructions
1. `pnpm create vite frontend --template react-ts`; `cd frontend; pnpm install`; `pnpm add -D vitest @testing-library/react @testing-library/jest-dom jsdom`.
2. `vite.config.ts`: proxy `/api` → `http://localhost:8000` with the `/api` prefix stripped; Vitest `environment: 'jsdom'`.
3. `src/shared/api.ts`: `apiGet<T>(path): Promise<T>` using `fetch('/api' + path)`; throws on non-2xx with the status; base override via `import.meta.env.VITE_API_URL` when set.
4. `src/health/HealthBadge.tsx`: on mount fetch `/health`; states `loading` / `ok` (status ok and db up) / `degraded` (db down) / `unreachable` (fetch error). Text and colour per state.
5. `App.tsx`: title "TraceForge", header with `HealthBadge`, an "Incidents" section that says "No incidents yet" (no fake rows).
6. `src/health/HealthBadge.test.tsx`: mock `fetch` for the four states.
7. Taskfile: `web` (`pnpm --dir frontend dev`), `web:test` (`pnpm --dir frontend test -- --run`), `web:build`. If P0-S02 merged first, add these to the existing Taskfile in this PR.
8. README: frontend section with commands.

Edge cases: backend down → `unreachable`, not a blank page; slow backend → loading state visible.

## F. Checklist
- [ ] Vite React-TS app created with pnpm and lockfile
- [ ] Vitest + Testing Library configured
- [ ] Dev proxy to the API
- [ ] `shared/api.ts` with error handling
- [ ] `HealthBadge` with four states from the real response
- [ ] Tests for all four states
- [ ] Taskfile entries
- [ ] README section
- [ ] Screenshots of "API ok" and "API unreachable" attached to TRAC-2

## G. Expected deliverables
New: `frontend/` (Vite app, `src/shared/api.ts`, `src/health/*`). Modified: `Taskfile.yml`, `README.md`.

## H. Testing and validation
- `task web:test` green.
- Manual: `task dev` + `task web` → "API ok"; stop the db → "degraded"; stop the API → "unreachable".
- Acceptance: status text comes only from the response mapping, never hardcoded.

## I. Dependencies and integration
- **Depends on:** P0-S01; uses P0-S02's endpoint.
- **Unblocks:** P3-S03 (reviewer UI), P3-S04 (results page).

## J. Definition of done
Merged after Rafique's review; tests pass; screenshots on TRAC-2; works on both laptops against the real backend.
