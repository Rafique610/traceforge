# RC2 dev validation (EXPERIMENTAL-RC2-DEV) - facts only

- Provider/model: Ollama local qwen3.5-4b-ctx12k, condition G1, replicate 0, dev manifest, --no-db, runs/rc2-dev. Shared GPU.
- Selection: first 4 of the seeded 10 (seed 20261125, sorted dev configuration cases): shop_api-001, 032, 056, 071. shop_api-071 evidence was collected locally (lab_collect, zero tokens).
- Excluded: the earlier BeatAPI rc1 run rc2dev-shop_api-001-rc1 failed with provider 503 (NO_PATCH); it is a failed provider run and not part of the comparison.

| case | rc1 outcome / attempts / tokens | rc2 outcome / attempts / tokens | rc2 truncations | rc2 repeat-guard |
|---|---|---|---|---|
| shop_api-001 | REJECTED (visible_failed) / 3 / 37701+4179 | NO_PATCH (output_truncated) / 2 / 33159+9978 | 0 | 0 |
| shop_api-032 | NO_PATCH (budget_exhausted) / 0 / 65343+3990 | NO_PATCH (budget_exhausted) / 0 / 64829+3860 | 0 | 0 |
| shop_api-056 | TEST_VERIFIED_IN_LAB / 1 / 19499+1435 | TEST_VERIFIED_IN_LAB / 1 / 19499+1435 | 0 | 0 |
| shop_api-071 | NO_PATCH (budget_exhausted) / 0 / 66074+4313 | NO_PATCH (budget_exhausted) / 0 / 66074+4313 | 0 | 0 |

- Outcome differences rc1 vs rc2: 1 of 4 (shop_api-001: REJECTED vs NO_PATCH; different model samples, not attributable to RC2 since no rc2 events fired).
- rc2 log events: none in any run (no rationale truncations, no repeat-guard triggers).
- hidden_fragment_hits: 0 in all 8 runs. rc1 meta fingerprint ee3d8d87...6456b51; rc2 meta carries the RC2 fingerprint.
- Caveats: n is tiny (4 cases, 1 replicate); temperature 0 is not guaranteed deterministic; DEV validation only, no blind validation claim (needs unseen test cases and AxForge spend not approved).
- Raw: runs/rc2-dev/summary.json, runs/rc2-dev/rc2dev-ollama-*/.
