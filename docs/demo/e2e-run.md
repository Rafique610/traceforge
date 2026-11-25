# Real end-to-end investigation run (facts)

Date 2026-11-24. Real path, no fake gateway: uvicorn (backend venv) on :8000 against dev Postgres
(`traceforge-db-1`, localhost:5433, alembic at head 0002), vite dev server on :5173 proxying `/api` -> :8000.
Provider BeatAPI free profile (`glm-5.3-flash-free`) through the existing gateway/limiter. No keys were read or printed.

## Commands
```
# evidence, zero tokens (real lab from faulty tree, ~45 s each)
python -m traceforge.agent.lab_collect --case shop_api-001 --out ../runs/real-e2e/evidence   # also -017, -002, -111
# server (env: TRACEFORGE_LLM_PROVIDER=beatapi TRACEFORGE_LLM_MODEL=glm-5.3-flash-free
#   TRACEFORGE_MANIFEST=datasets/manifests/dev.json TRACEFORGE_EVIDENCE_DIR=runs/real-e2e/evidence)
python -m uvicorn traceforge.main:app --port 8000 ; npx vite --port 5173
python scripts/e2e_investigate.py --case shop_api-001 --decision reject   # via http://localhost:5173/api
```
Artifacts: `runs/real-e2e/` (logs, report-*.json, events-*.json, evidence/).

## Results
| run | case | states reached | time | outcome |
|---|---|---|---|---|
| 1 | shop_api-017 (config) | CREATED, SNAPSHOT_LOCKED, CONTEXT_RETRIEVED, INCONCLUSIVE, REVIEW_PENDING, REVIEWED, CLOSED (approve) | 500 s | insufficient_evidence: "No trace_frame evidence collected". The lab-collected bundle for 017 has no failure signal (POST /orders returned 201; fault is only visible via tests). |
| 2 | shop_api-001 (config; bundle has 6 trace frames) approve | same chain | 20 s | provider_error 503 InternalServerError, process-wide halt latch (by design) |
| 3 | 001 reject (same server) | same | 20 s | zero calls: halt latch from run 2 |
| 4 | 001 reject (server restarted, latch reset) | same | 263 s | provider_error: beatapi call failed (503): InternalServerError; not retried |

Never reached: DIAGNOSED, PATCH_PROPOSED, VALIDATING, VERIFIED/UNVERIFIED. Blocker: BeatAPI returned HTTP 503 on the first
diagnosis call in runs 2 and 4 (not 429/402/403). Run 1 ended inconclusive on evidence grounds (the provider outcome of its
calls was not separately inspected). Total real provider attempts by this agent: a handful (run 1 plus one each in runs 2 and 4).

## Verified live
- POST /incidents (201), POST /incidents/{id}/investigate (202), polling GET /incidents/{id} to REVIEW_PENDING, through the vite proxy.
- GET report json and `?format=md`: well-formed; INCONCLUSIVE root cause, `outcome.missing_evidence` populated with the honest reason, evidence list (33-40 items with sha256, trace frames with lab/ paths for 001), `patch: null`, `limitations` set.
- POST /incidents/{id}/review approve (run 1) and reject (run 4): 201, state REVIEWED -> CLOSED; second review on a closed incident: 409.
- Audit trail (GET /incidents/{id}/events) has created, 3 system transitions, agent INCONCLUSIVE + REVIEW_PENDING + `missing_evidence`, `reviewer:e2e-human` REVIEWED, system CLOSED.
- No hidden test id, `hidden_tests` or `datasets/` string appears in any report or event payload saved.
- Vite proxy routes `/api/health`, `/incidents`, `/events`, `/evidence`, `/report` all 200; `/` serves the SPA. No browser run.

## Not verified
- Populated patch/impact fields, validation runs, VERIFIED path, approve-with-patch-hash and reject-with-patch-hash (covered only by unit tests), patch never touching lab/ or datasets/ (no patch produced), hidden tests absent from LLM prompts (the HiddenLeakGuard wraps the chat fn but no prompt was inspected here).

## Observations (not changed)
- Incidents created with only `case_id` have `service` and `symptom` null in the report header (`incidents/service.create_incident` does not copy the manifest service). Cosmetic.
- The BeatAPI halt latch is per process: after one 503 every later incident in the same uvicorn gets zero calls until restart.
- Lab-collected evidence for most dev config/code cases carries no failing request, so the v5 pipeline relies on the test symptom; case 001 is the only dev case with trace frames.
- No code was changed.

Servers (uvicorn, vite) stopped; lab compose projects were torn down by lab_collect.

## Addendum: provider ollama (qwen3.5-4b-ctx12k, local), 2026-11-24
Server env: `TRACEFORGE_LLM_PROVIDER=ollama TRACEFORGE_LLM_MODEL=qwen3.5-4b-ctx12k` (same manifest/evidence dir); vite proxy as before.
| run | case | states | time | outcome |
|---|---|---|---|---|
| A | shop_api-001 | ... CONTEXT_RETRIEVED, then investigation_failed | 22 s | defect (fixed): DIAGNOSED guard "evidence_ids contains ids not stored" |
| B | shop_api-001 (approve) | ... CONTEXT_RETRIEVED, DIAGNOSED, REVIEW_PENDING, REVIEWED, CLOSED | 595 s | correct diagnosis: configuration / `shop_api.REDIS_HOST` (4 evidence ids, SUPPORTED); no patch: `failure_reason=malformed_edit` (4B model could not produce a valid edit); reproducer validation run recorded failed (0 pass/1 fail); `patch` null, report limitation "NOT verified" |
| C | shop_api-017 (reject) | ... CONTEXT_RETRIEVED, INCONCLUSIVE, REVIEW_PENDING, REVIEWED, CLOSED | 635 s | insufficient_evidence (no trace frames in the lab bundle) |
PATCH_PROPOSED/VERIFIED were not reached: a valid result for this model, not retried. Reject path verified live on a no-patch incident (017); approve live on 001 (no patch). Patch-hash review paths remain unit-test-only.
Fixes: (1) `investigation.py` `_SymptomPersistingEvidence`: the v5 pipeline stored the raw bundle then appended symptom items, so citing them failed the DIAGNOSED guard; the full bundle is now stored first (test `tests/incidents/test_symptom_evidence.py`). (2) `incidents/router.py` fills `service` from the manifest when an incident is created with only `case_id` (header now shows `shop_api`; symptom stays null: the manifest has none; test in `test_incidents_api.py`). `pytest tests/incidents`: 196 passed.
Checks: sha256 over all files in `lab/` and `datasets/` identical before/after; no hidden test id or `hidden_tests` string in these reports/events or the uvicorn log (prompts not captured, so only the guard wrapper vouches for them). Servers stopped. Run A's incident cb937469 remains stuck in CONTEXT_RETRIEVED (pre-fix).

## Addendum: BeatAPI re-run, 2026-11-24 (after coordinator reported recovery)
shop_api-001 (approve), incident 449db95f: CONTEXT_RETRIEVED -> INCONCLUSIVE -> REVIEW_PENDING -> REVIEWED -> CLOSED in 198 s. Provider again returned `503 InternalServerError` on the diagnosis call (halted, not retried; no loop, no second case run). No patch; PATCH_PROPOSED/VERIFIED not reached, patch/impact/approve-with-hash/reject-with-hash unverified. lab/ and datasets/ hashes unchanged. Stuck incident cb937469 (pre-fix ollama run A, CONTEXT_RETRIEVED) left untouched. Servers stopped.

## Owner-gated step (open)
The patch, impact and validation fields and approve-with-patch-hash have not been exercised on a strong model through the real path: BeatAPI free returned HTTP 503 at the first diagnosis call and the local 4B model produced `malformed_edit`. `agent/axforge.py` blocks every AxForge request until the owner confirms the free-allowance billing check, so this needs one action from the owner (about 30k tokens, slot per `TRACEFORGE_AXFORGE_KEY_SLOT`):

```
cd backend
.venv/Scripts/python.exe -m traceforge.agent.e2e --case shop_api-001 --condition G1 --provider axforge --axforge-billing-verified --label EXPERIMENTAL-DEMO
```

Note: the "No code was changed" line under the first run predates the two fixes recorded later in this file (symptom evidence stored before the pipeline; `service` filled from the manifest).

## BeatAPI patch check (2026-11-25, after the final sync)
`agent.e2e --case shop_api-056 --condition G1 --provider beatapi --model glm-5.3-flash-free` (one case, no retries): HTTP 503 InternalServerError at the first diagnosis call after 298 s, 6,806 tokens in, 2,863 out, outcome NO_PATCH. This is the third 503 on this provider at the diagnosis step even though a short smoke call succeeds, so the free model is not usable for the investigation prompt. The patch stage on a strong model remains the owner-gated AxForge run above.
