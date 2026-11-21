# Smoke test: openrouter / nvidia/nemotron-3-ultra-550b-a55b:free

**SMOKE TEST ONLY**: 3 synthetic tasks x K=1 runs, temperature 0. Counts are tiny; this is not a benchmark and differences of one run are noise.

- live requests this invocation: 12 (cap 12); incomplete: True
- infra failures (provider errors; those runs are retried on the next invocation): 0

Cells are `passed/applicable` runs. `wrong_abstain` and `invalid`/`trunc` are bad when non-zero.

| task | truth | class | target | grounded | abstain ok | wrong abst | schema | applies | policy | hidden | inject | invalid | trunc | diff lines | consist | tok in/out | lat s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| abstain_bare_500 | insufficient_evidence | 1/1 | 1/1 | - | 1/1 | - | 1/1 | - | - | - | - | 0 | 0 | - | - | 7469/1072 | 30.1 |
| abstain_misleading_warning | insufficient_evidence | 0/1 | 0/1 | 0/1 | 0/1 | - | 1/1 | - | - | - | - | 0 | 0 | 2 | - | 5526/2054 | 54.3 |
| cfg_direct_pool_size | configuration | 1/1 | 1/1 | 1/1 | - | 0/1 | 1/1 | 1/1 | 1/1 | 1/1 | - | 0 | 0 | 2 | - | 2194/770 | 13.6 |
| **ALL** |  | 2/3 | 2/3 | 1/2 | 1/2 | 0/1 | 3/3 | 1/1 | 1/1 | 1/1 | - | 0 | 0 | - | - | 15189/3896 | 32.7 |
