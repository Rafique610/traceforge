# P1-S01 — Lab fixtures

## A. Task identification
| Field | Value |
|---|---|
| Phase | 1 Core components |
| Step | 1 |
| Task ID | P1-S01 |
| Synverk card | TRAC-5 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Normal (critical path) |
| Effort | 2.5 days |
| Status | NOT STARTED |
| Branch | `rafique/P1-S01-lab-fixtures` |

## B. Objective
Build the healthy "victim" system that every fault is injected into: an HTTP API and a non-HTTP queue worker sharing Postgres and Redis. Diagnosis needs to know what *should* happen, so each service ships a written contract and tests. The code is deliberately spread over several modules so that faults can have a cause far from the symptom (distance ≥1), which is what gives graph retrieval room to help.

## C. Prerequisites
- P0-S02 merged (Taskfile, conventions).
- Docker Desktop running; Python 3.12 + uv.
- Read `docs/invariants/security.md` (no credentials in Compose), [ARCHITECTURE.md](../ARCHITECTURE.md#research-design) (distance).

## D. Technical background
- The lab is **not** part of TraceForge's own app; it has its own Compose project (`lab/compose.yaml`) and its own Postgres, so breaking it never breaks the control plane (assumption AS5).
- A non-HTTP worker shows the product isn't limited to web pages and gives "same symptom, different cause" pairs (broker host wrong vs Redis down).
- Distance examples to make possible: settings read in `settings.py` but failing in `queue.py`; a helper in `services/pricing.py` returning bad data that crashes in `handlers/orders.py`; the worker consuming a queue name set on the API side.

## E. Implementation instructions
1. **`lab/shop_api/`** (its own uv project, FastAPI + SQLAlchemy):
   - modules: `app/settings.py` (Pydantic: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `REDIS_HOST`, `REDIS_PORT`, `ORDER_QUEUE`), `app/db.py`, `app/models.py` (products, orders), `app/services/catalog.py`, `app/services/pricing.py`, `app/routes/products.py`, `app/routes/orders.py`, `app/queue.py` (enqueue order-confirmation jobs), `app/main.py`.
   - endpoints: `GET /products`, `GET /products/{id}`, `POST /orders`, `GET /orders/{id}/total`, `GET /health`.
   - `CONTRACT.md`: per endpoint: input, output, edge cases (empty catalogue → `[]`; missing → 404; quantity ≤0 → 422; total = sum(price × qty) rounded to 2 dp).
   - seed data script (`app/seed.py`) with a few products.
2. **`lab/worker/`**: `worker/settings.py` (`REDIS_HOST`, `REDIS_PORT`, `ORDER_QUEUE`, DB settings), `worker/queue.py` (BRPOP loop), `worker/handlers.py` (confirm order → write status), `worker/retry.py` (max 3 retries with backoff), `worker/heartbeat.py` (SET `worker:heartbeat` with 15 s TTL), `worker/main.py`. `CONTRACT.md` for job format and retry rules.
3. **Tests** per service under `lab/<service>/tests/`: unit tests for services/handlers; one integration test using the running Compose stack (marked `integration`). These are the **visible/public** tests; hidden tests are created later per case (P1-S03).
4. **Dockerfiles** two-stage (uv build stage → slim runtime), non-root user. Images tagged `traceforge-lab/shop_api:dev` and `traceforge-lab/worker:dev` (the sandbox reuses them).
5. **`lab/compose.yaml`**: `shop_api`, `worker`, `lab_db` (postgres:16), `lab_redis` (redis:7); healthchecks; credentials only `${LAB_*}` from `.env`; `depends_on` with `condition: service_healthy`.
6. **Probes:** `lab/probes/check_api.py` (GET /health), `lab/probes/check_worker.py` (heartbeat key exists).
7. **Taskfile:** `lab:up`, `lab:down`, `lab:reset` (down -v + up + seed), `lab:test`, `lab:probe`.
8. **`.gitattributes`** rule `lab/** text eol=lf` (if not added in P0-S01).
9. README: lab section.

Edge cases: worker starts before Redis → retry connect, don't crash-loop silently; DB empty → API returns `[]`, not 500 (the healthy baseline must satisfy its own contract).

## F. Checklist
- [ ] shop_api modules and endpoints
- [ ] shop_api `CONTRACT.md`
- [ ] worker modules, retry and heartbeat
- [ ] worker `CONTRACT.md`
- [ ] Logic spread across modules to allow distance ≥1 faults (list 5 candidate fault sites in the PR description)
- [ ] Unit + integration tests per service
- [ ] Two-stage, non-root Dockerfiles; image tags fixed
- [ ] `lab/compose.yaml` with healthchecks and `${VAR}` credentials
- [ ] Probes
- [ ] Taskfile entries
- [ ] `.gitattributes` LF rule
- [ ] README section
- [ ] Runs on both laptops

## G. Expected deliverables
New: `lab/shop_api/`, `lab/worker/`, `lab/probes/`, `lab/compose.yaml`. Modified: `Taskfile.yml`, `.env.example` (LAB_* names), `README.md`.

## H. Testing and validation
- `task lab:up` → 4 containers healthy; `task lab:probe` both OK.
- `task lab:test` green; `POST /orders` results in a confirmed order written by the worker within 10 s.
- Manual edge cases: empty catalogue → `[]`; stopping Redis → API `/health` reports Redis down and worker heartbeat disappears (this is the `runtime_dependency` symptom later).
- Acceptance: contracts describe every endpoint/job; tests cover each contract line.

## I. Dependencies and integration
- **Depends on:** P0-S02.
- **Unblocks:** P1-S02 (images), P1-S03 (mutation targets), P2-S01 (evidence source), P2-S02 (code to graph).
- **Integration:** lab paths become `gold_symbols` paths in manifests; keep module paths stable once P1-S03 starts.

## J. Definition of done
Merged after Ruhan's review; lab healthy and tests green on both laptops; contracts written; candidate distance ≥1 fault sites listed; TRAC-5 approved.
