# P2-S05 — Evidence report and hash-bound review

## A. Task identification
| Field | Value |
|---|---|
| Phase | 2 Evidence-to-repair |
| Step | 5 |
| Task ID | P2-S05 |
| Synverk card | TRAC-16 |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | — |
| Reviewer | Muhammad Rafique |
| Priority | Normal |
| Effort | 1.5 days |
| Status | NOT STARTED |
| Branch | `ruhan/P2-S05-report-review` |

## B. Objective
Give the engineer the output they act on: a report built deterministically from stored records (no LLM, so it can't hallucinate), and an approve/reject decision that can only apply to the exact patch it was made on.

## C. Prerequisites
- P1-S04 (incidents, audit), P2-S04 (patches, validation runs).
- Report template: Appendix A of the earlier architecture doc (reproduced below).

## D. Technical background
- The report is assembled from DB rows: incident, evidence items, hypotheses/diagnosis, patch, validation runs, model usage. Each claim carries an ID (`EV-…`, test ID, `patch_sha256`).
- The review request includes `patch_sha256`; the service compares it with the frozen patch's hash. Mismatch → 409. Reviews are insert-only; a second review creates a new row and audit event, never edits the old one.
- Non-repairable outcomes still get a report: runtime_dependency names the failing dependency and its evidence; insufficient_evidence lists what evidence was missing.

## E. Implementation instructions
1. **`reports/builder.py`:** `build_report(db, incident_id) -> Report` (Pydantic) with sections: header (case, service, base SHA, origin), symptom (+ evidence IDs), root-cause status (SUPPORTED / INCONCLUSIVE / RUNTIME_DEPENDENCY) with cause class and target, evidence chain, competing hypotheses (supporting/contradicting IDs), repair (patch SHA, changed paths, diff), red baseline / green patch (test IDs and outcomes), hidden suite result, model usage (model ID, prompt hash, tokens, list-price cost, latency), reviewer decision, limitations (fixed text by outcome).
2. **`reports/render.py`:** Markdown rendering of `Report`.
3. **`reports/router.py`:** `GET /incidents/{id}/report` (JSON; `?format=md` returns Markdown).
4. **`reviews/models.py`:** `Review` (id, incident_id, patch_sha256, decision `approve`/`reject`, reviewer name, comment, created_at) + migration.
5. **`reviews/service.py`:** validate state is `REVIEW_PENDING`; compare hash with the frozen patch (or allow no-hash for `NO_PATCH` outcomes); insert; transition to `REVIEWED`; audit event.
6. **`reviews/router.py`:** `POST /incidents/{id}/review` with `ReviewCreate` schema (decision enum, `patch_sha256` hex length 64, comment ≤ 2000 chars, reviewer name ≤ 80).
7. **Tests:** report for each of the four outcome classes (fixtures in DB); every evidence ID in the report exists; tampered hash → 409; review on wrong state → 409; review rows immutable (no update path).

Edge cases: incident without patch asking for a hash → 422; second review after `REVIEWED` → allowed as a new row? **Decision:** no — one review per frozen patch in A3; a new patch would need a new incident run.

## F. Checklist
- [ ] `Report` model and builder from DB records only
- [ ] Markdown renderer
- [ ] Report endpoint (JSON + MD)
- [ ] Review model + migration
- [ ] Review service with hash check, state check, audit
- [ ] Review endpoint with constrained schema
- [ ] Tests for 4 outcome classes, tamper, wrong state, immutability
- [ ] Report for a seed case pasted on TRAC-16

## G. Expected deliverables
New: `backend/traceforge/reports/{builder,render,router}.py`, `backend/traceforge/reviews/{models,schemas,service,router}.py`, migration, tests. Modified: `main.py`, `README.md`.

## H. Testing and validation
- All tests green; manual check in `/docs`: GET report for a verified seed case; POST review with the right hash → 201; with a changed character → 409.
- Acceptance: no field in the report is produced by an LLM; every ID resolves.

## I. Dependencies and integration
- **Depends on:** P1-S04, P2-S04.
- **Unblocks:** P2-S07, P3-S03 (UI shows report and review).

## J. Definition of done
Merged after Rafique's review; tests pass; a real seed-case report reviewed through the API; TRAC-16 approved.
