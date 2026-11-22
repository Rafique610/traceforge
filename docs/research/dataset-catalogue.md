# Dataset catalogue (P1-S03 → P3-S01)

Status: **VALIDATED and test split FROZEN on 22 Nov 2026** (`datasets/manifests/test.sha256` = `881f288763a8…`; record in `freeze.json`, per-case results in `validation.json`). Every number below comes from `python -m traceforge.faultgen.generate` on 22 Nov 2026. Nothing is final until `task dataset:validate` (3 sandbox runs per suite) passes and the test split is hashed.

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

## Validation and freeze (22 Nov 2026)
- **Validator:** `task dataset:validate:shards` runs 4 parallel shards. Every suite runs 3 times on the original, the faulty and the gold-fixed tree, in the locked-down sandbox. Shard 1 holds the live outage checks, because they share one Docker project.
- **First run** (55 min): 173/184 passed. The 11 rejections were fixed in the generator, not waived:
  - 8 database-outage cases failed on the original tree because `psycopg` was missing from the sandbox image. It was added.
  - 3 settings values crashed the app at import time (`Decimal("0,17")`, `"4.99.0"`, `"5O.00"`), so pytest produced no report. They were replaced by request-time wrong values.
- **Final run** (about 1 h, on the final image): **184/184 passed, 0 flaky, 13/13 live outage checks ok** (real `lab_redis` / `lab_db` stopped and restored).
- **Frozen test split:** 151 cases. 60 configuration, 67 application_code, 12 runtime_dependency, 12 insufficient_evidence; 35 variant groups; 20 fault families; 115 shop_api and 36 worker; 127 (84%) at distance ≥1. The lab `base_sha` is `5ec94a43f8b9…`. The experiment runner's freeze guard accepts it.

## Still open after the freeze
- **D28 (author bias) was not done.** All sites were written by Rafique's session; nobody else wrote or blind-reviewed 25% of them. Report it as a threat to validity.
- **Graph distances are manual estimates.** Computed `codeintel` distances can be added to the analysis as a second column. Changing `test.json` now would break the freeze.
- **`log_format` is a label only** (D24): the lab does not switch log formats per case.
- **Near-duplicates:** settings groups have up to 9 wrong values. Report per group as well as per case.
- **Ruhan's 10-label peer check** is not done (owner decision: all work stays here).

## Commands
```powershell
task dataset:generate
```
```powershell
task dataset:validate:shards
```
```powershell
task dataset:freeze
```
