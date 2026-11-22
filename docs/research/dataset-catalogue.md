# Dataset catalogue (P1-S03 → P3-S01)

Status: **batches 1 + 2 generated, all count targets met; NOT validated, NOT frozen.** Every number below comes from `python -m traceforge.faultgen.generate` on 22 Nov 2026. Nothing is final until `task dataset:validate` (3 sandbox runs per suite) passes and the test split is hashed.

## How cases are made
1. **Lab growth (P1-S01 extension).** `shop_api` gained stock reservation (`inventory.py`), coupons (`coupons.py`), shipping and tax (`shipping.py`) and a price quote (`quote.py`). New endpoints are `GET /orders/{id}/quote` and `GET /products/low-stock`, plus a 409 when an order exceeds stock. Seven new settings come with them. This is about 150 lines of app code and 10 public tests, and `CONTRACT.md` is updated.
2. **Sites.** `faultgen/templates/sites.py` lists realistic wrong lines: 16 code sites and 7 settings-default sites, each with up to 5 wrong versions (variants). Ruhan's original 3 code sites and the 2 Redis settings fields are reused.
3. **Tests found by running the code.** For each variant, `faultgen/scenarios.py` runs the correct and the faulty tree through the real endpoints on in-memory SQLite, over a fixed pool of inputs. It keeps the inputs where the answers differ. The reproducer uses the visible pool and the hidden tests use a disjoint hidden pool, so no input literal is shared (D31). Expected values are whatever the correct code returns. A variant that no endpoint can observe is dropped (2 were dropped in batch 1).
4. **Split by group.** All variants of one site share a `variant_group`, and whole groups go to dev or test. The dev groups are fixed in `catalogue.py` before any tuning. Case ids are opaque (`shop_api-NNN`), assigned in a seeded shuffle.

## Counts after batch 2 (generated, unvalidated)
| Split | Cases | configuration | application_code | runtime_dependency | insufficient_evidence | Groups | Families | Services | Distance ≥1 |
|---|---|---|---|---|---|---|---|---|---|
| test | **151** | **60** | **67** | **12** | **12** | 35 | 20 | shop_api 115, worker 36 | 127 (84%) |
| dev | **33** | 16 | 15 | 1 | 1 | 11 | 10 | shop_api 28, worker 5 | 31 |
| **Target** | test ≥144, dev ≥30 | ≥60 | ≥60 | ≥12 | ≥12 | | ≥10 | | ≥50% |

8 wrong versions were dropped automatically because no public behaviour could see them. One dev group, `code:worker:job_validation`, therefore has no cases left.

### Batch 2 added
- **Worker sites** (`templates/worker_site_data.py`):
  - retry count, last-retry boundary and backoff formula;
  - dead-letter queue, retry budget, job validation and malformed-job routing;
  - settings `max_retries`, `backoff_base_s` and `order_queue`. The last one covers the API-vs-worker queue-name pattern: the API pushes to the contract name, and a worker with a wrong default never sees the job.

  A worker scenario runs one real job through `consume_once` and observes taken / calls / sleeps / dead letters / left.
- **Outages** (`templates/outages.py`):
  - runtime groups: broker down seen through `/health`, database down seen through `/health`, database down seen through `/products`;
  - insufficient-evidence groups: sporadic 503s, flapping health, unconfirmed orders.

  The live runtime check now supports `lab_db` as well as `lab_redis`.
- The sandbox runner adds the workdir's parent to `PYTHONPATH`, and the validator picks the sandbox config by service, so worker cases run.

## Still open before freeze
- **Validate** every case: `task dataset:validate -- --manifest test.json` and `-- --manifest dev.json`. That is about 3 minutes per repairable case, roughly 8–9 hours, run in the background. Live runtime checks need `task lab:build` and `lab/.env`.
- **Graph distances**: replace manual distances with `codeintel`-computed ones where they differ.
- **`log_format` is a label only.** The lab does not yet switch formats per case (D24).
- **D28**: Ruhan writes or blind-reviews at least 25% of the sites before any graph tuning.
- **Near-duplicates**: settings groups have up to 8 wrong values each. All stay in one split, but analysis should report per group as well as per case.

## Commands
```powershell
task dataset:generate
```
```powershell
task dataset:validate -- --manifest test.json
```
