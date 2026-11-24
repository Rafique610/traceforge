# P3-S03 — Reviewer UI

## A. Task identification
| Field | Value |
|---|---|
| Phase | 3 Dataset, evaluation and UI |
| Step | 3 |
| Task ID | P3-S03 |
| Synverk card | TRAC-21 (screenshot required) |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | — |
| Reviewer | Muhammad Rafique |
| Priority | Normal |
| Effort | 4 days |
| Status | IMPLEMENTED, TESTED, NOT REVIEWED/APPROVED |
| Branch | `ruhan/P3-S03-reviewer-ui` |

**Status sync 2026-11-25.** Evidence: vitest 12 files / 78 tests; ReviewPanel focus/ARIA fixes; Investigate button enabled with polling and accessible errors. Not verified against a live backend with a real provider. Five-fact detail: `docs/plans/RUHAN_TASK_TRACKER.md`.

## B. Objective
The live-demo surface (rubric C2, E1): an engineer goes from incident to decision without a terminal. The page order follows how an engineer reasons: symptom → evidence → where in the code → why → what changed → did it pass → decide.

## C. Prerequisites
- P0-S03 (scaffold), P1-S04 (incident endpoints), P2-S05 (report/review), P2-S06 (GitHub intake), P2-S07 (investigate endpoint). Can start earlier against contract samples and the OpenAPI schema.
- Read `docs/invariants/frontend.md`.

## D. Technical background
- Data comes from: `GET /incidents`, `POST /incidents`, `POST /incidents/from-github`, `POST /incidents/{id}/investigate`, `GET /incidents/{id}`, `/events`, `/evidence`, `/report`, `POST /incidents/{id}/review`.
- Investigation is async: poll `GET /incidents/{id}` every 2 s while state is not terminal; stop on `REVIEW_PENDING`, `REVIEWED`, `UNVERIFIED`, `INCONCLUSIVE`.
- Types: generate TS types from the OpenAPI schema (`openapi-typescript`) so UI and API can't drift.
- Real data only; empty/loading/error states for every panel.

## E. Implementation instructions
1. `pnpm add react-router-dom`; `pnpm add -D openapi-typescript`; `task web:types` generates `src/shared/api-types.ts` from `http://localhost:8000/openapi.json`.
2. **`src/incidents/IncidentList.tsx`:** table (created, service, symptom, state, cause class); filters by state; "New incident" opens a form with two tabs: from lab case (dropdown of dev case IDs from an endpoint or manifest file) / from GitHub URL.
3. **`src/incidents/IncidentDetail.tsx`** sections in order:
   1. Header: state badge, service, base SHA, source.
   2. Symptom with linked evidence IDs.
   3. Evidence timeline (`EvidenceList`: kind icon, ID, content excerpt, expand).
   4. Ranked code/config hits with reasons (from the report's context section).
   5. Diagnosis: cause class, target, supporting vs contradicting evidence (clickable IDs scroll to evidence).
   6. Diff viewer (simple unified-diff renderer with +/− colouring; no heavy dependency unless needed).
   7. Tests: reproducer before/after, visible, hidden pass/fail.
   8. Model usage: model, tokens, latency, list-price cost.
   9. "Investigate" button (disabled while running).
4. **`src/review/ReviewPanel.tsx`:** approve/reject + comment + reviewer name; sends `patch_sha256` from the report; shows the stored decision after submit; handles 409 with a clear message ("the patch changed since you loaded it").
5. Non-repairable outcomes: detail shows "No patch: runtime dependency `<service>` is failing (evidence …)" or "Inconclusive: missing …".
6. Vitest: data mapping for each outcome class; review form validation and 409 handling.
7. UX pass with the **impeccable** skill; attach screenshots of list, detail (verified case), detail (runtime_dependency), review.

## F. Checklist
- [ ] Router and generated API types
- [ ] Incident list with filters
- [ ] Create from lab case / GitHub URL
- [ ] Detail page sections 1–9 in order
- [ ] Polling during investigation
- [ ] Diff viewer
- [ ] Review panel with hash and 409 handling
- [ ] Non-repairable outcome views
- [ ] Empty/loading/error states everywhere
- [ ] Vitest tests
- [ ] impeccable UX pass
- [ ] Screenshots on TRAC-21

## G. Expected deliverables
New: `frontend/src/incidents/*`, `frontend/src/review/*`, `frontend/src/shared/{api-types.ts,DiffView.tsx}`. Modified: `App.tsx`, `Taskfile.yml`, `README.md`. Possibly a small backend endpoint listing available case IDs (coordinate with Rafique).

## H. Testing and validation
- `task web:test` green.
- Manual walkthrough on a seed case of each class against the real backend.
- Acceptance: no value on any page is hardcoded; tampered-hash path shows the 409 message.

## I. Dependencies and integration
- **Depends on:** P0-S03, P2-S05 (and the endpoints listed).
- **Unblocks:** P4-S03 (demo), P6-S03 (polish).

## J. Definition of done
Merged after Rafique's review; full flow clickable for all four classes; screenshots attached; TRAC-21 approved.
