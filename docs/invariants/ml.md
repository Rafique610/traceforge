# Data, evaluation and experiments

## Splits and leakage
- Dev split (prompt/weight tuning, debugging) and held-out test split are separate and frozen. The test manifest is hashed (SHA-256) before any reported run.
- Split by template variant group so near-duplicates never cross splits.
- Gold patches, mutation targets and hidden tests never appear in model-visible text.
- Gold labels come from the fault generator when the bug is seeded, never from agent output.

## Fair comparisons
- Within one experiment, hold model ID and version, temperature, prompts, tools, context budget, time limit and attempt count fixed. Only the factor under test changes.
- Model comparisons are a separate experiment from retrieval/feedback ablations.
- Report numerators, denominators, per-category breakdowns, failures and negative results. No best-of-N without saying so.
- Repeated runs on the same case are not independent samples: use paired statistics.

## Records
- Every run saves: dataset hash, condition, model ID, prompt hash, seed, tool trace, tokens, cost, latency, outcome. Metrics are recomputed from saved artifacts by a script.
- Model provider and free-tier limits are recorded with the run; a provider change is an ADR.
