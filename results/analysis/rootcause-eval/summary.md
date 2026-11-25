# Root-cause / impact evaluation results (reduced P5-S16)

Deterministic across two full runs: **True**; result digest `6d6a5bd34dee24a4`; priors sha256 `290be1d1dca28762`; token cap 600, top-k 20.

## Preregistered thresholds

| # | Threshold | Result | Measured |
|---|---|---|---|
| R1 | A: RC top1 >= G top1, RC MRR >= G MRR, gold in top 3 for both A cases | FAIL | `{"G_mrr": 0.6, "G_top1": 0.5, "RC_mrr": 0.6, "RC_ranks": {"A1": 1, "A2": 5}, "RC_top1": 0.5}` |
| R2 | B+C: RC top5 >= G top5 + 0.125 and RC top5 >= 0.75 | FAIL | `{"G_top5": 0.625, "RC_top5": 0.5, "diff_ci95": [-0.375, 0.0]}` |
| R3 | B+C: RC top5 >= BM25 top5 | PASS | `{"BM25_top5": 0.375, "RC_top5": 0.5, "diff_ci95": [-0.375, 0.625]}` |
| R4 | D: RC gold key in top 3 for >= 3/4 | PASS | `{"BM25_top3": 0.0, "G_top3": 0.75, "RC_top3": 1.0}` |
| R5 | A,B,C,D,G at equal 600-token cap: RC dep recall >= G and RC dep precision >= G | FAIL | `{"BM25": [0.9028273809523809, 0.2502900745088245], "G": [0.9875, 0.3796705898268398], "RC": [0.9660714285714286, 0.3788825757575757]}` |
| R6 | G: gold in top 3 for both and mean decoys in top 5 <= 1.0 | PASS | `{"RC_ranks": {"G1": 3, "G2": 1}, "mean_decoys_top5": 1.0}` |
| R7 | H: abstains on both; false abstention on non-H <= 1 | PASS | `{"H_abstained": 2, "H_gold_top5": {"BM25": 2, "G-distance": 0, "RC-overlay": 0, "RC-overlay+bm25": 2}, "H_n": 2, "false_abstain": 0, "non_H_n": 16}` |
| R8 | F: macro selection recall >= 0.90 and detection 5/5 | PASS | `{"detected": 1.0, "sel_recall": 1.0}` |
| R9 | F: macro fraction of suite selected <= 0.75 | PASS | `{"frac_suite": 0.5753246753246752}` |
| R10 | F: macro direct-dependant recall >= 0.90 and affected-dependant recall >= 0.80 | PASS | `{"dep_recall": 1.0, "direct_recall": 1.0}` |
| R11 | F: macro impact-report precision >= 0.70 | PASS | `{"dep_precision": 1.0}` |
| R12 | F: mean false-positive warnings per patch <= 1.0 | PASS | `{"fp_flags": 0.0}` |
| R13 | hidden isolation: 0 hidden-path strings in any report | PASS | `{"IMP-graph": 0.0, "IMP-overlay": 0.0}` |
| R14 | determinism: two full runs identical | PASS | `{"result_digest": "6d6a5bd34dee24a4e25e1331d4305ad3cd8c6f12f2a90e230b43a39e89f4c53f"}` |
| R15 | latency: RC median <= 2000 ms, max <= 5000 ms | PASS | `{"BM25_median": 5.375200009439141, "G-distance_median": 1.636600005440414, "RC-overlay_max": 58.10539997764863, "RC-overlay_median": 34.79069999593776}` |
| R16 | (informational) IMP-overlay selection recall >= BM25-select at equal k | PASS | `{"BM25-select": 0.5392857142857143, "IMP-overlay": 1.0}` |

Go/no-go by the preregistered rule: S12 **no-go**, S15 **go**.

## Root-cause ranking by family (mean over cases)

| Family | n | Arm | top1 | top3 | top5 | MRR | dep recall | dep precision | tokens |
|---|---|---|---|---|---|---|---|---|---|
| A | 2 | RC-overlay | 0.500 | 0.500 | 1.000 | 0.600 | 1.000 | 0.472 | 251 |
| A | 2 | RC-overlay+bm25 | 0.500 | 0.500 | 1.000 | 0.600 | 1.000 | 0.348 | 338 |
| A | 2 | G-distance | 0.500 | 0.500 | 1.000 | 0.600 | 1.000 | 0.414 | 214 |
| A | 2 | BM25 | 0.500 | 0.500 | 1.000 | 0.600 | 1.000 | 0.219 | 576 |
| B | 4 | RC-overlay | 0.250 | 0.500 | 0.750 | 0.479 | 0.950 | 0.346 | 490 |
| B | 4 | RC-overlay+bm25 | 0.250 | 0.500 | 0.750 | 0.473 | 0.950 | 0.236 | 582 |
| B | 4 | G-distance | 0.250 | 0.500 | 1.000 | 0.487 | 0.950 | 0.345 | 452 |
| B | 4 | BM25 | 0.000 | 0.250 | 0.500 | 0.228 | 0.938 | 0.286 | 563 |
| C | 4 | RC-overlay | 0.000 | 0.000 | 0.250 | 0.136 | 0.914 | 0.418 | 491 |
| C | 4 | RC-overlay+bm25 | 0.000 | 0.000 | 0.250 | 0.133 | 0.843 | 0.287 | 592 |
| C | 4 | G-distance | 0.000 | 0.000 | 0.250 | 0.134 | 1.000 | 0.455 | 440 |
| C | 4 | BM25 | 0.000 | 0.000 | 0.250 | 0.119 | 0.757 | 0.271 | 564 |
| D | 4 | RC-overlay | 0.500 | 1.000 | 1.000 | 0.750 | 1.000 | 0.340 | 392 |
| D | 4 | RC-overlay+bm25 | 0.500 | 1.000 | 1.000 | 0.750 | 1.000 | 0.340 | 392 |
| D | 4 | G-distance | 0.000 | 0.750 | 0.750 | 0.369 | 1.000 | 0.294 | 476 |
| D | 4 | BM25 | 0.000 | 0.000 | 0.750 | 0.204 | 0.917 | 0.239 | 594 |
| G | 2 | RC-overlay | 0.500 | 1.000 | 1.000 | 0.667 | 1.000 | 0.350 | 351 |
| G | 2 | RC-overlay+bm25 | 0.500 | 1.000 | 1.000 | 0.667 | 1.000 | 0.350 | 356 |
| G | 2 | G-distance | 0.500 | 0.500 | 0.500 | 0.583 | 1.000 | 0.433 | 336 |
| G | 2 | BM25 | 0.500 | 0.500 | 0.500 | 0.562 | 1.000 | 0.190 | 593 |
| H | 2 | RC-overlay | 0.000 | 0.000 | 0.000 | 0.000 | 0.500 | 1.000 | 35 |
| H | 2 | RC-overlay+bm25 | 0.000 | 1.000 | 1.000 | 0.417 | 1.000 | 0.500 | 162 |
| H | 2 | G-distance | 0.000 | 0.000 | 0.000 | 0.000 | 0.500 | 1.000 | 35 |
| H | 2 | BM25 | 0.000 | 1.000 | 1.000 | 0.500 | 1.000 | 0.160 | 587 |

## Per case (rank of the first acceptable root cause; `-` = not in the top 20)

| Case | RC-overlay | RC+bm25 | G-distance | BM25 | abstain |
|---|---|---|---|---|---|
| A1 | 1 | 1 | 1 | 1 | False |
| A2 | 5 | 5 | 5 | 5 | False |
| B1 | 2 | 2 | 2 | 14 | False |
| B2 | 1 | 1 | 1 | 2 | False |
| B3 | 4 | 4 | 5 | 11 | False |
| B4 | 6 | 7 | 4 | 4 | False |
| C1 | 19 | 19 | 17 | 5 | False |
| C2 | 5 | 5 | 5 | 12 | False |
| C3 | 6 | 6 | 6 | 9 | False |
| C4 | 8 | 9 | 9 | 12 | False |
| D1 | 2 | 2 | 2 | 4 | False |
| D2 | 1 | 1 | 3 | 4 | False |
| D3 | 1 | 1 | 2 | 4 | False |
| D4 | 2 | 2 | 7 | 15 | False |
| G1 | 3 | 3 | 6 | 8 | False |
| G2 | 1 | 1 | 1 | 1 | False |
| H1 | - | 2 | - | 2 | True |
| H2 | - | 3 | - | 2 | True |

## Change impact (family F, macro over 5 patches)

| Arm | selection recall | suite fraction | detected | dep recall | direct recall | dep precision | FP flags/patch | report tokens |
|---|---|---|---|---|---|---|---|---|
| BM25-select | 0.539 | 0.575 | 1.000 | n/a | n/a | n/a | n/a | n/a |
| IMP-graph | 0.600 | 0.348 | 0.800 | 0.550 | 0.600 | 1.000 | 0.000 | 650 |
| IMP-overlay | 1.000 | 0.575 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 969 |
| full-suite | 1.000 | 1.000 | 1.000 | n/a | n/a | n/a | n/a | n/a |

Hand-predicted failing sets equal to the measured ones: 5 of 5.

Small-n caveat: 23 hand-built cases from two toy projects; one case moves a family rate by 25-50 points. No superiority claim is made; thresholds were decided before the run on point estimates.

