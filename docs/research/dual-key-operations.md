# AxForge dual-key operations

Model: `glm-5.3-flash` only. Code: `backend/traceforge/agent/axforge.py`, `backend/traceforge/evaluation/scheduler.py`, `scripts/parallel_eval.py`. No key value is stored in any file or doc; only the slot name is recorded.

## Slots and enabling
| | Slot 1 | Slot 2 |
|---|---|---|
| Env var (name only) | `AXFORGE_API_KEY` | `AXFORGE_API_KEY2` |
| Ledger | `runs/axforge_usage.jsonl` | `runs/axforge_usage_k2.jsonl` |
| Pacing state | `runs/axforge_pacing.json` | `runs/axforge_pacing_k2.json` |
| Ceiling | 3,000,000 tokens | 3,000,000 tokens |

Slot 2 is enabled only if `AXFORGE_API_KEY2` is set AND `runs/axforge_keys_verified.json` contains `{"slot2_enabled": true}`. A process picks its slot with `TRACEFORGE_AXFORGE_KEY_SLOT` (the runner's `--axforge-key`). Each slot has its own in-flight reservation, 30 s pacing clock, 429/Retry-After block and halt flag.

## Ceilings
- 3M per slot (hard: no request that could cross it is sent).
- 4.8M combined planning ceiling across both slots (checked when slot 2 is enabled).
- 1.2M reserve: the gap between the 6M raw sum of both allowances and the 4.8M combined ceiling. It is not a separate constant in the code; it is kept unspent by the combined ceiling.
- Across processes the combined check relies on the other slot's ledger (margin: one request's worst case).

## Failure policy
- Halt on the first failure of a slot (provider error, 429, budget, refusal); no automatic retry anywhere.
- A failed job stays failed until a person re-queues it (`--retry-failed`); the runner then resumes from saved records.
- Failover applies only to pending work that has not started: jobs with slot `auto` and satisfied dependencies move to the healthy slot; jobs pinned to a halted slot stay pending.
- A recorded Retry-After keeps a slot cooling without halting it. A scheduler restart clears halted flags (deliberate act); one job runs per slot at a time; a file lock refuses two schedulers.

## Verified facts and unknowns
- Verified: both keys authenticate to `glm-5.3-flash`.
- Verified: a simultaneous start on both keys produced no 429, so RPM does not appear shared at that scale (small sample).
- Owner-stated, not provable through the API: key 2 belongs to a new account with a 3M allowance (quota independence).
- Ledger: key 1 stands at 2,847,367 of 3,000,000 committed. The owner believes key 1 has more remaining on the provider dashboard; the ledger is the conservative authority until the owner supplies a dashboard number. The true provider-side remaining balance is unknown.

## Provider priority policy
1. No API call if the task does not need one.
2. BeatAPI for development.
3. AxForge only for approved official experiments, the final evaluation and the viva.

Usage is recorded separately for BeatAPI, AxForge key 1 and AxForge key 2 (never merged). Report: `python -m traceforge.evaluation.usage_report` (from `backend/`).
