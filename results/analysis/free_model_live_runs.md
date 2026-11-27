# Free-model live runs (26–27 Nov 2026)

All runs use the real Investigate path (`POST /incidents/{id}/investigate`): real repo build, real symptom run in the Docker sandbox, real evidence, retrieval, diagnosis, patch, sandbox validation and the review state. The model is BeatAPI `glm-5.3-flash-free` (free tier, `reasoning_effort=low` default since 6732715, 4,096-token cap per call, 90 s pause between calls). The paid model was not used.

Raw logs are local and git-ignored: `runs/validation/repeat-free/` (logs + `summary.csv`), `runs/validation/bugsinpy/`, usage ledger `runs/beatapi_usage.jsonl`.

## 1. Repeat test on planted dev bugs: 18/18 correct

6 dev bugs × 3 independent runs, 26 Nov 2026 21:47–23:58. No provider errors and no retries.

| Bug | What it needs | Result (3 runs) | Patch | AI calls per run | Longest answer (tokens) |
|---|---|---|---|---|---|
| shop_api-002 | code fix (`OrderItemIn`) | TEST_VERIFIED_IN_LAB 3/3 | identical every run (`3550f1c8`) | 3 / 4 / 3 | 275 |
| shop_api-011 | code fix (`quote`) | TEST_VERIFIED_IN_LAB 3/3 | identical (`f0a04f92`) | 7 / 6 / 2 | 801 |
| shop_api-017 | config fix (`shop_api.MAX_DISCOUNT_PCT`) | TEST_VERIFIED_IN_LAB 3/3 | identical (`3c250661`) | 2 / 2 / 2 | 1,471 |
| shop_api-032 | config fix (`shop_api.LOW_STOCK_LEVEL`) | TEST_VERIFIED_IN_LAB 3/3 | identical (`500df840`) | 7 / 7 / 7 | 476 |
| shop_api-003 | Redis stopped: diagnose, no patch | `runtime_dependency` 3/3 | none (correct) | 4 / 4 / 2 | 594 |
| shop_api-004 | too little evidence: abstain | `insufficient_evidence` 3/3 | none (correct) | 1 / 1 / 1 | 190 |

**Before vs after the 25 Nov fixes** (streaming, 4,096 cap, low reasoning): before, 4 of 10 live runs ended with no result (3 answers cut off, 1 provider outage). After, 0 of 18 did.

**Caveats:** the bugs were planted by us in our own lab app; 6 distinct bugs, so the effective n is 6; identical patch hashes show the system is reproducible, not that it generalizes. Run time was 2–15 min per run, mostly the forced 90 s pauses.

## 2. Independent real bugs (BugsInPy, P5-S05): pilot

Real bugs from FastAPI's own git history (BugsInPy dataset), not written by us. Each has the project's own test, which fails before the real fix and passes after.

**Validation in our sandbox (27 Nov 2026), python 3.8, the bug's pinned dependencies:** of 15 candidates (fastapi bugs 2–16, all within our patch limit), **14 kept** and 1 dropped:
- bug 16 was dropped because its test already passes on the buggy code in our environment;
- every kept bug failed before the real fix and passed after, twice each;
- each kept bug has a fully green regression suite of 141–437 FastAPI tests, made of the project's own test files that pass with the real fix (files that cannot import in the sandbox, such as the tutorial tests, are left out).

Details: `runs/external/bugsinpy/validation.json` (local).

**Wiring check (no AI):** a stand-in model that submits the known fix took bug 5 through the full Investigate path to TEST_VERIFIED, with no hidden-test text in any prompt.

**Live free-model run:** bug 5 only; the free-token budget ran out before the 14-bug batch. Result: see section 3.

**Limits to state on the slide:**
- code bugs only; there is no Docker runtime evidence, so the only evidence is the failing test's output;
- the model may have seen these public 2019–2020 fixes during training (contamination);
- the hidden suite is the same test file as the reproducer, so it adds no new behaviour;
- line endings are normalized to LF, which changes no behaviour.

## 3. Live result on the real bug

| Bug | Real fix | Outcome | Notes |
|---|---|---|---|
| bugsinpy-fastapi-5 | `fastapi/utils.py::create_cloned_field` (1 line) | **No result** (inconclusive, not counted as a fix or a failure) | Try 1 (11:46): provider unreachable, no AI call (an outage, not an AI failure). Try 2 (12:11): 6 AI calls, every answer very short (14–50 output tokens, ~9k input), then the runner's 25-min time limit killed it before a diagnosis was submitted. Its log is empty (output was buffered). Stopped there by the owner to save free tokens |

**Reading.** The pipeline works on this real bug (the stand-in run verified it), but the free model did not produce a diagnosis on it within the time limit. The short answers suggest it kept making tool calls (reading code) instead of submitting. On a repo much larger than the lab, that's plausible but unconfirmed, because the log was lost. **Do not present this as a result; present the validation and the stand-in run.**

**Fixed for the next run:** `scripts/live_batch.sh` now runs unbuffered (`PYTHONUNBUFFERED=1`, so a killed run still leaves its log) with a 45-min limit.

Remaining 13 validated bugs: not run (out of free tokens this week). Command: `bash scripts/live_batch.sh 0 "2 3 4 6 7 8 9 10 11 12 13 14 15"` (see `docs/plans/HANDOFF_TO_RUHAN.md` section 4).
