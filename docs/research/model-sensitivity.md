# Model sensitivity (P5-S04): glm-5.3-flash vs local qwen3.5-4b-ctx12k

Facts only. Experimental, label `EXPERIMENTAL-LOCAL-P5S04`. Not part of the 2x2 and not part of `results/final`.

## What was compared
- glm-5.3-flash: the recorded RC1 G1 run (`results/final/final-axforge-G1`, replicate 0, AxForge provider, pipeline v5). Not re-run.
- qwen3.5-4b-ctx12k: local Ollama, built `FROM qwen3.5:4b-q4_K_M`, `num_ctx 12288`, temperature 0, 3.3 GB. Run now with `python -m traceforge.agent.e2e --condition G1 --provider ollama --model qwen3.5-4b-ctx12k --manifest datasets/manifests/test.json --no-db --out runs/p5s04`, one case at a time (`scripts/p5s04_run.py`), each wrapped by `HwMonitor` (2 s). Same 12 stage-1 sites (`results/final/selection-rc1.json`), same evidence bundles (`runs/evidence`), replicate 0.
- `qwen2.5-coder:7b` is not installed and was not downloaded. No code-specific local model was compared. The comparison is exactly these two models.
- Earlier Qwen smoke failure (HTTP 400): Ollama rejected a prompt longer than its default 4096 context. The 12k variant removes this; no case in this run hit a context error.

## Results (12 sites, 1 replicate)
| | glm-5.3-flash (RC1) | qwen3.5-4b-ctx12k (local) |
|---|---|---|
| Verified repairs (TEST_VERIFIED_IN_LAB, hidden pass) | 10 | 4 (008, 181, 119, 019) |
| Diagnosis class correct | 12 | 9 (wrong: 066 and 148 abstained, 030 abstained instead of runtime_dependency) |
| Abstentions | 1 (102, correct) | 4 (066, 148, 030 wrong; 102 correct) |
| Outcomes | 10 verified, 2 NO_PATCH | 4 verified, 4 REJECTED (malformed_edit), 4 NO_PATCH |
| Invalid tool calls (recorded) | 0 | 26 total |
| Latency per case, median / P95 | 24.0 s / 28.6 s | 275.6 s / 406.5 s |
| Tokens in / out (total) | 37,417 / 543 | 536,188 / 42,992 |
| Output tokens per second (tokens_out / case latency; includes prompt processing and tool rounds, so a floor, not decode speed) | median 1.6 | median 15.5 |
| GPU memory peak | n/a (remote) | 4,917 MiB of 6,144 (Ollama already held ~4.9 GB before runs) |
| System RAM used peak | n/a (remote) | 16,251 MiB (whole machine, 16 GB, other processes included) |

Failure reasons recorded for the local model: malformed_edit (4), budget_exhausted (2), model_output_malformed (1), insufficient_evidence (1). No timeouts (12 min cap not reached; max case 449 s), no provider/context errors. Per case rows: `results/p5s04/table.csv`; aggregates: `results/p5s04/summary.json`; hardware samples per case: `results/p5s04/hw/`; raw runs: `runs/p5s04/`.

## Hardware (closes open question Q9 for the machine used)
GPU NVIDIA GeForce GTX 1660 SUPER, 6 GB (6,144 MiB), driver 621.14; CPU Ryzen 5 2600; 16 GB RAM; Windows 11 Pro. Ollama at localhost:11434. This is one machine; other team members' hardware was not measured here.

## Limitations
- n = 12 sites, 1 replicate: differences are descriptive, no significance claim.
- Different model classes (hosted flash model vs 4B quantised local model) and different providers; no claim about which model is better.
- The RC1 glm run used pipeline-v5 tuning and the G1F1 setting (patch step shared the diagnosis from G0, `patch_from final-axforge-G0`); the local run used the CLI's own G1 flow. Not comparable to the RC1 pipeline-v5 tuning.
- Local runs are not under the final-evaluation guard (no RC1 fingerprint run-guard, no `results/final` registration). Hidden-test leak guard of the e2e CLI was active.
- Latency for glm is the recorded model latency from RC1 (remote, rate-paced); local latency is on a shared desktop. Not like-for-like.
- GPU peak is dominated by the resident model (~4.9 GB); RAM figure is machine-wide.
- A first launch accidentally started two drivers concurrently; those partial results were discarded and the run restarted cleanly with one driver (kept for transparency at `runs/p5s04_aborted_concurrent` and `results/p5s04/aborted_concurrent_attempt`; not used in the table).
- Case order was interleaved by cause class; all 12 cases completed within budget (~60 min).
