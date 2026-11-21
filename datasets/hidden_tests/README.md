# Hidden tests

Acceptance tests for seeded fault cases. **Never** placed inside `lab/` and never exposed to the model: not in the context bundle, the retrieval index, tool output or test feedback (the agent only ever sees pass/fail of the final gate, per `docs/invariants/security.md`).

## Convention
```
datasets/hidden_tests/<service>/<test_file>.py     # service = shop_api | worker
```
Case manifests reference them as `hidden_test_ids`, e.g. `datasets/hidden_tests/shop_api/test_orders_hidden.py::test_empty_cart_total_zero`.

- Tests import the lab code like the visible ones (`app.*`, `worker.*`) and must run with plain pytest in the disposable sandbox worktree, no Docker unless the case needs it.
- The sandbox runner copies the hidden file into the worktree only for the final run, after the patch is applied, and deletes it afterwards.
- The directory is created empty; the tests are written in the seed-case task (P1-S03).
