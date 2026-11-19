# P0-S05 — Shared contracts and sample JSON

## A. Task identification
| Field | Value |
|---|---|
| Phase | 0 Foundation |
| Step | 5 |
| Task ID | P0-S05 |
| Synverk card | TRAC-4 |
| Primary owner | Muhammad Rafique |
| Supporting | Muhammad Ruhan Kamran (pair session) |
| Reviewer | Both approve |
| Priority | High |
| Effort | 1 day (pair) |
| Status | NOT STARTED |
| Branch | `rafique/P0-S05-contracts` |

## B. Objective
Fix the five data shapes the two tracks exchange, with realistic samples, so that each person can build their whole lane against samples without waiting. This is the **only** planned cross-track dependency before Sync 1.

## C. Prerequisites
- P0-S02 merged (contracts live in `backend/traceforge/contracts/`).
- Both members available for one session (about 2–3 hours).
- Read [INTEGRATION_PLAN.md](../INTEGRATION_PLAN.md#contracts) and the research design in [ARCHITECTURE.md](../ARCHITECTURE.md#research-design).

## D. Technical background
- Pydantic v2 models give validation, JSON (de)serialization and JSON Schema in one place. Enums use `Literal[...]` or `StrEnum`.
- Paths in contracts are **repo-relative POSIX** strings (`lab/shop_api/app/products.py`), never absolute Windows paths.
- `distance` is the number of graph hops from where the symptom surfaces to where the cause lives (0 = traceback points straight at the bug). It drives the research analysis.
- `AgentRunRecord` carries everything needed to recompute every metric later, so no metric depends on logs.

## E. Implementation instructions
1. Create `backend/traceforge/contracts/` with one file per contract: `case_manifest.py`, `evidence.py`, `context.py`, `test_run.py`, `agent_run.py`, and `__init__.py` re-exporting them.
2. **`CaseManifest`** fields: `case_id: str`, `split: Literal["dev","test"]`, `cause_class: Literal["configuration","application_code","runtime_dependency","insufficient_evidence"]`, `fault_family: str`, `service: Literal["shop_api","worker"]`, `base_sha: str`, `gold_config_keys: list[str]`, `gold_symbols: list[GoldSymbol]` (`path`, `qualname`, `start_line`, `end_line`), `distance: int | None` (None for no-target cases), `reproducer_id: str`, `visible_test_ids: list[str]`, `hidden_test_ids: list[str]`, `variant_group: str`, `origin: Literal["synthetic","bugsinpy"]`. Validator: repairable classes need at least one gold key or symbol.
3. **`EvidenceBundle`**: `incident_id`, `base_sha`, `compose_sha256`, `items: list[EvidenceItem]`; `EvidenceItem` = `id` (e.g. `EV-0001`), `kind: Literal["log","health","config","trace_frame","compose","issue"]`, `service`, `content` (already redacted), `sha256`, optional `path`, `line`, `ts`.
4. **`ContextBundle`**: `incident_id`, `mode: Literal["L","G"]`, `token_budget`, `tokens_used`, `hits: list[ContextHit]` (`node_id`, `kind: Literal["symbol","config_key","test","file"]`, `path`, `start_line`, `end_line`, `score`, `reasons: list[str]`, `excerpt`). Validator: `tokens_used <= token_budget`.
5. **`TestRunRequest`**: `case_id`, `worktree_path`, `suite: Literal["visible","hidden","reproducer"]`, `timeout_s: int = 120`. **`TestRunResult`**: `passed`, `failed`, `tests: list[TestOutcome]` (`id`, `outcome: Literal["passed","failed","error","skipped"]`), `stdout_tail` (≤4 KB), `duration_ms`, `timed_out`, `error: str | None`.
6. **`AgentRunRecord`**: fields as in the integration plan, including `condition: Literal["L0","G0","L1","G1"]`, `outcome: Literal["TEST_VERIFIED_IN_LAB","REJECTED","UNVERIFIED","NO_PATCH"]`, `diagnosis: Diagnosis`, `dataset_sha256`, `git_sha`, cost fields (`cost_usd` actual, `list_price_usd` equivalent).
7. **Samples** in `contracts/samples/`: for each contract, three files: a config case (distance 1: `REDIS_HOST` read in `worker/settings.py`, failure raised in `worker/queue.py`), a code case (empty-list indexing in `shop_api`), and an abstain case. Contents must look like real lab output (realistic log lines, tracebacks, line numbers).
8. Test `backend/tests/test_contract_samples.py`: every sample validates; `model_dump_json` → parse → equal.
9. `task contracts:schema` writes JSON Schema to `contracts/schema/` (handy for the frontend later).
10. README: "Changing a contract" rule (own PR, both approve, additive within a phase).

## F. Checklist
- [ ] Pair session held; field list agreed and noted on TRAC-4
- [ ] Five contract modules created
- [ ] Validators (repairable needs target; tokens within budget)
- [ ] Repo-relative POSIX paths documented in docstrings
- [ ] 3 realistic samples per contract
- [ ] Sample round-trip test
- [ ] JSON Schema export task
- [ ] README rule
- [ ] Both approved the PR

## G. Expected deliverables
New: `backend/traceforge/contracts/*.py`, `contracts/samples/*.json`, `contracts/schema/*.json`, `backend/tests/test_contract_samples.py`. Modified: `Taskfile.yml`, `README.md`.

## H. Testing and validation
- `task test` passes; deliberately break one sample field → test fails.
- Each member writes a 5-line stub consumer for one contract they will use and confirms it reads the sample (not committed if throwaway).
- Acceptance: both members confirm in the PR that they can start Phase 1 with these samples alone.

## I. Dependencies and integration
- **Depends on:** P0-S02.
- **Unblocks:** P1-S02, P1-S04, P1-S06 (via P1-S04), P2-S01, P2-S03, P3-S02, and every stub in [INTEGRATION_PLAN.md](../INTEGRATION_PLAN.md#interfaces-between-modules-function-level).

## J. Definition of done
Contracts and samples merged with both approvals; tests green; the change rule is in the README; TRAC-4 lists the agreed fields.
