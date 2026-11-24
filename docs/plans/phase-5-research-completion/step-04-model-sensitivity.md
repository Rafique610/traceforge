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
| Status | PARTIALLY COMPLETE (local comparison done: 12 sites, one replicate; research run complete for the feasible local alternative; not Reviewed/Approved) |
| Branch | `ruhan/P5-S04-model-sensitivity` |

**Status sync 2026-11-25 (final).** Evidence: IMPLEMENTED, TESTED (`agent/hw_monitor.py`, 3 tests). Local comparison 25 Nov: 12 stage-1 sites, G1, replicate 0, one at a time, `qwen3.5-4b-ctx12k` (= qwen3.5:4b-q4_K_M, num_ctx 12288; the earlier HTTP 400 root cause was Ollama's default 4096 context rejecting the prompt) vs recorded glm-5.3-flash (RC1): verified repairs 10 vs 4; diagnosis class correct 12 vs 9; abstentions 1 vs 4 (1 correct); invalid tool calls 0 vs 26; median/P95 latency per case 24.0/28.6 s vs 275.6/406.5 s (max 449 s, no timeouts, no context errors); GPU peak 4,917 of 6,144 MiB; RAM peak 16,251 MiB machine-wide; of 8 non-verified local cases 4 REJECTED (malformed_edit), 4 NO_PATCH. No code model compared (qwen2.5-coder:7b not installed, nothing downloaded). Not mixed into the 2x2 or `results/final`; n=12, one replicate; Ryzen 5 2600, 16 GB, GTX 1660 SUPER 6 GB (this machine only; Q9 closed for it). `docs/research/model-sensitivity.md`. Five-fact detail: `docs/plans/RUHAN_TASK_TRACKER.md`.

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
