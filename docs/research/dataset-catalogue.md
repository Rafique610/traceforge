# Dataset catalogue (P1-S03 → P3-S01)

Status: **batch 1 generated, NOT validated, NOT frozen.** Every number below comes from `python -m traceforge.faultgen.generate` on 22 Nov 2026. Nothing is final until `task dataset:validate` (3 sandbox runs per suite) passes and the test split is hashed.

## How cases are made
1. **Lab growth (P1-S01 extension).** `shop_api` gained stock reservation (`inventory.py`), coupons (`coupons.py`), shipping and tax (`shipping.py`) and a price quote (`quote.py`). New endpoints are `GET /orders/{id}/quote` and `GET /products/low-stock`, plus a 409 when an order exceeds stock. Seven new settings come with them. This is about 150 lines of app code and 10 public tests, and `CONTRACT.md` is updated.
2. **Sites.** `faultgen/templates/sites.py` lists realistic wrong lines: 16 code sites and 7 settings-default sites, each with up to 5 wrong versions (variants). Ruhan's original 3 code sites and the 2 Redis settings fields are reused.
3. **Tests found by running the code.** For each variant, `faultgen/scenarios.py` runs the correct and the faulty tree through the real endpoints on in-memory SQLite, over a fixed pool of inputs. It keeps the inputs where the answers differ. The reproducer uses the visible pool and the hidden tests use a disjoint hidden pool, so no input literal is shared (D31). Expected values are whatever the correct code returns. A variant that no endpoint can observe is dropped (2 were dropped in batch 1).
4. **Split by group.** All variants of one site share a `variant_group`, and whole groups go to dev or test. The dev groups are fixed in `catalogue.py` before any tuning. Case ids are opaque (`shop_api-NNN`), assigned in a seeded shuffle.

## Batch 1 counts (generated, unvalidated)
| Split | Cases | configuration | application_code | runtime_dependency | insufficient_evidence | Groups | Families | Distance ≥1 |
|---|---|---|---|---|---|---|---|---|
| test | 78 | 31 | 47 | 0 | 0 | 21 | 16 | 78 (100%) |
| dev | 28 | 11 | 15 | 1 | 1 | 10 | 9 | 26 |
| **Target** | test ≥144, dev ≥30 | ≥60 | ≥60 | ≥12 | ≥12 | | ≥10 | ≥50% |

## Gaps before freeze (batch 2)
- **Configuration −29 and code −13 (test).** The next sites to add:
  - worker settings: `max_retries`, `backoff_base_s`, `connect_attempts`;
  - a mismatch between the API's and the worker's queue name (the "worker fails on an API-side setting" pattern);
  - `order_queue`;
  - worker code faults in the retry and dead-letter path.

  This needs the validator to run worker cases: it is hard-wired to `lab/shop_api` today (`validate.py` `SANDBOX_CFG`).
- **runtime_dependency −12 and insufficient_evidence −12.** There is only one template of each. Variants are needed for a stopped database, stopped Redis, a stopped worker, and several silent symptoms with logs withheld.
- **Distances are manual estimates.** P3-S01 asks for the graph-computed distance. Run `codeintel` distance on every case before the freeze and replace manual values where they differ.
- **`log_format` is a label only.** Code cases are tagged `uvicorn_access` and config cases `plain`, but the lab does not actually switch log formats. D24 needs the lab to emit JSON or no logs per case, or the label must be dropped from the analysis.
- **D28 (author bias).** Ruhan writes or blind-reviews at least 25% of the sites in `sites.py` before any graph tuning.
- **Validation time.** About 3 minutes per repairable case, so roughly 8–9 hours for 174 cases, run in background batches once the lab stops changing. Every lab change alters `base_sha` and forces regeneration.

## Commands
```powershell
task dataset:generate
```
```powershell
task dataset:validate -- --manifest test.json
```
