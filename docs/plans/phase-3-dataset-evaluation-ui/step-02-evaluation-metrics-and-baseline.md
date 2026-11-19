# P3-S02 — Evaluation metrics, rule-based baseline and failure export

## A. Task identification
| Field | Value |
|---|---|
| Phase | 3 Dataset, evaluation and UI |
| Step | 2 |
| Task ID | P3-S02 |
| Synverk card | TRAC-20 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Normal |
| Effort | 2.5 days |
| Status | NOT STARTED |
| Branch | `rafique/P3-S02-eval-metrics` |

## B. Objective
Every number shown in the demo is computed here from saved records (rubric D2, D5; avoids the "unverifiable claims" deduction), and the LLM diagnosis gets a simple deterministic baseline to beat (rubric D3, safeguard 3). Also exports failures for the ≥10 written analyses (D4).

## C. Prerequisites
- P0-S05 (`AgentRunRecord`, `CaseManifest`). Build on contract samples; real records arrive from P2-S07/P3-S04.
- Agree the report JSON shape with Ruhan on day one (P3-S04 renders it).

## D. Technical background
- **Retrieval:** Recall@5, MRR, nDCG@10 (binary relevance), tokens used. (E1 code from P2-S03 should import these functions.)
- **Diagnosis:** cause-class accuracy; exact-target top-1 (gold key/symbol matched); abstention precision and recall (positive class = should abstain); runtime_dependency precision/recall; misdiagnosis rate (confident wrong class).
- **Repair:** verified repair rate = `TEST_VERIFIED_IN_LAB` / repairable cases; patch apply rate; regressions (visible suite failures after patch).
- **System:** median and P95 latency, actual cost and list-price cost per case, invalid tool-call rate, cache-hit rate.
- **Breakdowns:** by `cause_class`, `fault_family`, `distance` bucket, condition.
- **Rule baseline:** deterministic mapping from evidence to class, for example:
  - dependency container unhealthy or absent → `runtime_dependency`;
  - connection error + configured host/port/queue ≠ healthy Compose service → `configuration` (target = that key);
  - traceback with top in-repo frame → `application_code` (target = that symbol);
  - none of the above → `insufficient_evidence`.
- **Paired comparison:** per-case difference between two conditions (used in P4-S01 and expanded in P5-S02).

## E. Implementation instructions
1. `evaluation/metrics/{retrieval,diagnosis,repair,system}.py`: pure functions over records + manifests.
2. `evaluation/baselines/rules.py`: `diagnose_by_rules(bundle: EvidenceBundle) -> Diagnosis`; `task eval:baseline SPLIT=dev` produces records with `condition="RULES"` (contract addition: allow `RULES` as a condition value — contract PR).
3. `evaluation/report.py`: `build_report(records, manifests) -> dict` with the agreed shape (sections: retrieval, diagnosis, repair, system, each with overall + breakdowns + n); `task eval:report RUNS=<dir>` writes `report.json` and prints tables.
4. `evaluation/failures.py`: export each failed case with gold vs predicted, retrieved hits, tool sequence, failed gate, and a blank `cause_category` (taxonomy below) for human analysis → `failures.csv`.
5. Taxonomy (from the architecture doc): `BAD_TRACE_MAPPING`, `DYNAMIC_DISPATCH_NOT_RESOLVED`, `MISBOUND_CONFIG_KEY`, `SIMILAR_SYMPTOM_WRONG_CAUSE`, `MISSED_DEPENDENCY`, `LOW_RETRIEVAL_RECALL`, `HALLUCINATED_CONTRACT`, `PATCH_FAILS_APPLY`, `TEST_ENVIRONMENT_FAILURE`, `TEST_OVERFIT`, `MISLEADING_LOG_INJECTION`, `INSUFFICIENT_EVIDENCE_NO_ABSTENTION`, `COST_OR_TIMEOUT`.
6. Unit tests with hand-computed examples for every metric (including edge cases: no gold in top-k → reciprocal rank 0; n=0 bucket → reported as n=0, not 0%).

## F. Checklist
- [ ] Retrieval metrics
- [ ] Diagnosis metrics incl. abstention and runtime_dependency
- [ ] Repair metrics
- [ ] System metrics (median, P95, both costs)
- [ ] Breakdowns by class, family, distance, condition
- [ ] Rule baseline + contract PR for `RULES`
- [ ] Report builder + agreed JSON shape documented
- [ ] Failure export with taxonomy column
- [ ] Unit tests with hand-computed values
- [ ] Baseline scored on dev; table pasted on TRAC-20

## G. Expected deliverables
New: `backend/traceforge/evaluation/{metrics/*,baselines/rules.py,report.py,failures.py}`, tests. Modified: contracts (additive), `Taskfile.yml`, `README.md`.

## H. Testing and validation
- Unit tests green; report from sample records matches a hand-made expected JSON.
- Acceptance: every metric's denominator is printed next to it.

## I. Dependencies and integration
- **Depends on:** P0-S05.
- **Unblocks:** P3-S04 (results page), P4-S01, P4-S02, P5-S02.

## J. Definition of done
Merged after Ruhan's review; tests green; baseline on dev reported; TRAC-20 approved.
