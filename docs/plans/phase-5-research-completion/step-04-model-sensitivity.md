# P5-S04 — Model sensitivity: Devstral vs local Qwen

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 4 |
| Task ID | P5-S04 |
| Synverk card | TRAC-29 |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | — |
| Reviewer | Muhammad Rafique |
| Priority | Low (A4) |
| Effort | 2 days |
| Status | PARTIALLY COMPLETE (setup and monitor only; NO model-comparison result) |
| Branch | `ruhan/P5-S04-model-sensitivity` |

**Status sync 2026-11-25.** Evidence: `agent/hw_monitor.py` + 3 tests; local Ollama models qwen3.5:4b-q4_K_M, medgemma:4b, all-minilm:22m (`qwen2.5-coder:7b` NOT installed). One smoke (shop_api-001, G1, qwen3.5:4b) ended provider_error BadRequestError (HTTP 400; cause unconfirmed). Five-fact detail: `docs/plans/RUHAN_TASK_TRACKER.md`.

## B. Objective
A separate experiment (never mixed into the 2×2) answering: how much does the result depend on the model? It also documents what a fully local, private, free deployment can achieve on a 6 GB GPU.

## C. Prerequisites
- P5-S03 G1 runs (or at least G1 for the subset); Ollama with `qwen2.5-coder:7b` (Q4).

## D. Technical background
- Same condition (G1), same cases, same contexts (re-use `ContextBundle`s saved from G1 runs), only the model changes.
- Local constraints: keep context ≤ 8K tokens; record tokens/s, VRAM peak (`nvidia-smi --query-gpu=memory.used`), RAM, wall time.
- Expected: weaker tool calling locally; report honestly (invalid tool-call rate is a key metric here).

## E. Implementation instructions
1. Condition file `G1_local.yaml` identical to G1 except model profile.
2. Run on the repairable subset (≥50) and the non-repairable cases; 1 replicate (note the limitation).
3. Collect VRAM/RAM/tokens-per-second samples during runs (`agent/hw_monitor.py`, sampling every 2 s).
4. Table: verified repair rate, diagnosis accuracy, abstention precision, invalid tool calls, median/P95 latency, tokens/s, VRAM peak — for both models.
5. Hardware note: GPU model, driver, VRAM for each member's laptop (closes open question Q9).

## F. Checklist
- [ ] `G1_local` condition
- [ ] Same contexts reused
- [ ] Runs complete
- [ ] Hardware monitor and samples
- [ ] Comparison table
- [ ] Hardware note; Q9 closed

## G. Expected deliverables
Condition file, hardware monitor, `evaluation/results/a4/model_sensitivity.json` + table.

## H. Testing and validation
- Context reuse verified (same bundle hashes in both runs).
- Acceptance: table numbers recompute from saved runs.

## I. Dependencies and integration
- **Depends on:** P5-S03 (G1).
- **Feeds:** P6-S04 (paper), business section (local deployment option).

## J. Definition of done
Merged after Rafique's review; table and hardware note published; TRAC-29 approved.
