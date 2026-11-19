# P5-S01 — Deeper graph and new fault families

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 1 |
| Task ID | P5-S01 |
| Synverk card | TRAC-24 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Low (A4) |
| Effort | 3 days |
| Status | NOT STARTED |
| Branch | `rafique/P5-S01-deeper-graph` |

## B. Objective
Address the graph weaknesses found in the A3 failure analysis (typically unresolved dynamic calls and missing cross-service links) and add harder, distance ≥2 fault families, so the A4 study covers cases where graph retrieval should matter most.

## C. Prerequisites
- A3 delivered; `failure_analysis.md` (P4-S02); graph decision ADR (see the phase README).

## D. Technical background
- **Runtime trace edges:** run each service's visible tests under `sys.settrace` or `coverage.py` dynamic contexts to record actual caller → callee pairs; add as `CALLS` edges with `source="trace"`, resolving many `unknown:` edges.
- **Cross-service config edges:** link a config key set in one service's Compose env to the other service's reads of the same semantic setting (e.g. `ORDER_QUEUE` on API and worker).
- **New families at distance ≥2:** e.g. a value produced in `pricing.py`, transformed in `orders.py`, crashing in `handlers.py`.
- **Test-set integrity:** the A3 frozen test set must not change. New families go into a new held-out manifest `test_a4_ext.jsonl` with its own hash.

## E. Implementation instructions
1. `codeintel/runtime_trace.py`: run visible tests in the sandbox with tracing (allow writing a trace file to `/out`); parse to edges; merge with confidence 0.9.
2. `codeintel/cross_service.py`: semantic config links (same key name across services; explicit mapping file for renamed equivalents).
3. Report the unknown-edge count before/after on the lab.
4. New templates for 2–3 distance ≥2 families; generate ≥30 cases into `test_a4_ext.jsonl` + dev variants; validate; freeze with `test_a4_ext.sha256`.
5. Re-run E1 on dev and on the new set; compare before/after graph versions (both reported, not replaced).
6. Tests for each new edge source.

## F. Checklist
- [ ] Graph decision ADR read and followed
- [ ] Runtime trace edges
- [ ] Cross-service config edges
- [ ] Unknown-edge count before/after
- [ ] 2–3 new distance ≥2 families
- [ ] New held-out set frozen separately
- [ ] E1 before/after reported
- [ ] Tests

## G. Expected deliverables
New: `codeintel/{runtime_trace,cross_service}.py`, new templates, `datasets/manifests/test_a4_ext.jsonl` + hash, tests. Updated E1 results.

## H. Testing and validation
- Original `test.sha256` unchanged (CI check).
- Acceptance: unknown-edge count drops; E1 table for both graph versions saved.

## I. Dependencies and integration
- **Depends on:** P4-S03, graph ADR.
- **Feeds:** P5-S03 (if the ADR says so), P6-S04 (paper).

## J. Definition of done
Merged after Ruhan's review; original test set untouched; new set frozen; E1 comparison reported; TRAC-24 approved.
