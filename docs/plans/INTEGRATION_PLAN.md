# Integration plan

The two tracks are built in parallel and integrated at three checkpoints. Integration is cheap only if the contracts are stable, so they come first and change only through a dedicated PR.

## Contracts
Location: `backend/traceforge/contracts/` (Pydantic v2), samples in `contracts/samples/*.json`. Defined in [P0-S05](phase-0-foundation/step-05-shared-contracts.md).

| Contract | Key fields | Producer | Consumer |
|---|---|---|---|
| `CaseManifest` | `case_id`, `split` (dev/test), `cause_class` (4 values), `fault_family`, `service`, `base_sha`, `gold_config_keys[]`, `gold_symbols[]` (path, qualname, start/end line), `distance`, `reproducer_id`, `visible_test_ids[]`, `hidden_test_ids[]`, `variant_group`, `origin` | Rafique (P1-S03, P3-S01) | Ruhan (P1-S06, P3-S04), Rafique (P3-S02) |
| `EvidenceBundle` | `incident_id`, `base_sha`, `compose_sha256`, `items[]` of `EvidenceItem` (`id`, `kind` log/health/config/trace_frame/compose/issue, `service`, `content` (redacted), `sha256`, `path?`, `line?`, `ts?`) | Rafique (P2-S01) | Ruhan (P1-S06 tools), Rafique (P2-S03 anchors) |
| `ContextBundle` | `incident_id`, `mode` (L/G), `token_budget`, `tokens_used`, `hits[]` of `ContextHit` (`node_id`, `kind` symbol/config_key/test/file, `path`, `start_line`, `end_line`, `score`, `reasons[]`, `excerpt`) | Rafique (P2-S03) | Ruhan (P1-S06 prompt) |
| `TestRunRequest` → `TestRunResult` | Request: `case_id`, `worktree_path`, `suite` (visible/hidden/reproducer), `timeout_s`. Result: `passed`, `failed`, `tests[]` (id, outcome), `stdout_tail`, `duration_ms`, `timed_out`, `error?` | Rafique (P1-S02) | Ruhan (P2-S04), Rafique (P1-S03 validator) |
| `AgentRunRecord` | `run_id`, `case_id`, `condition` (L0/G0/L1/G1), `model_id`, `provider`, `prompt_hash`, `diagnosis` (cause_class, target, evidence_ids, contradicting_ids, abstained), `patch_sha256?`, `attempts`, `outcome` (TEST_VERIFIED_IN_LAB/REJECTED/UNVERIFIED/NO_PATCH), `hidden_passed?`, `tokens_in`, `tokens_out`, `cost_usd`, `list_price_usd`, `latency_ms`, `tool_calls`, `invalid_tool_calls`, `cache_hits`, `dataset_sha256`, `git_sha` | Ruhan (P1-S06, P2-S04, P3-S04) | Rafique (P3-S02) |

**Rules**
1. A contract change is its own PR touching only `contracts/` (plus samples), approved by both, merged before dependent work.
2. Both sides keep a test that loads every sample. A contract change that breaks a sample fails CI on both sides.
3. Fields are only added (optional, with defaults) during a phase. Renames or removals wait for a sync point.

## Interfaces between modules (function level)
| Interface | Signature (proposed) | Owner |
|---|---|---|
| Evidence | `collect(incident_id, service, case: CaseManifest \| None) -> EvidenceBundle` | Rafique |
| Graph | `build_graph(repo_path, base_sha) -> Graph`; `distance(graph, a, b) -> int \| None` | Rafique |
| Retrieval | `retrieve(evidence: EvidenceBundle, graph, mode, token_budget) -> ContextBundle` | Rafique |
| Sandbox | `run_tests(TestRunRequest) -> TestRunResult` | Rafique |
| Gateway | `chat(messages, tools, *, model_profile, cache=True) -> ModelResponse` | Ruhan |
| Agent | `run_case(case_or_incident, condition) -> AgentRunRecord` | Ruhan |
| Metrics | `report(records: list[AgentRunRecord], manifests) -> dict` | Rafique |

Until the real producer exists, each consumer uses a **stub that reads the sample JSON** behind the same signature, so switching to the real one is a one-line change.

## Database integration
Only Track B writes the app database (`incidents`, `evidence_items`, `audit_events`, `patches`, `validation_runs`, `reviews`). Track A modules return contract objects; Track B persists them. This keeps migrations in one lane (Ruhan) and avoids two people editing Alembic history. The lab's own Postgres is separate from the app's Postgres.

## Integration order and checkpoints
| Checkpoint | Step | When | What gets joined | Must be stable before | Success test | Lead |
|---|---|---|---|---|---|---|
| C0 Contracts | [P0-S05](phase-0-foundation/step-05-shared-contracts.md) | End of Phase 0 | Data shapes | Nothing | All samples validate both sides | Rafique |
| C1 Sync 1 | [P1-S07](phase-1-core-components/step-07-sync-1-agent-on-seed-cases.md) | End of Phase 1 | Real `CaseManifest` → agent | P1-S03 validator green; P1-S06 runs on samples | 4 schema-valid `AgentRunRecord`s from real cases | Ruhan |
| C1b Sandbox | inside [P2-S04](phase-2-evidence-to-repair/step-04-repair-loop.md) | Phase 2 | Repair loop → real sandbox | P1-S02 merged | Seed config + code reach `TEST_VERIFIED_IN_LAB` | Ruhan |
| C2 Sync 2 | [P2-S07](phase-2-evidence-to-repair/step-07-sync-2-full-pipeline.md) | End of Phase 2 | Real evidence + context → agent → repair → report | P2-S01, P2-S03, P2-S04, P2-S05 merged | One command, 4 cases, both laptops | Rafique |
| C3 Results | [P3-S04](phase-3-dataset-evaluation-ui/step-04-experiment-runner-and-results-page.md) | Phase 3 | Runner records → metrics → UI | P3-S02 report format | Results page shows dev-run numbers | Ruhan |
| C4 Demo | [P4-S03](phase-4-a3-delivery/step-03-demo-and-submission-pack.md) | Phase 4 | Everything + GitHub intake + UI | All A3 steps | Clean-clone dry run | Ruhan |

## Integration testing
- `tests/integration/test_contract_samples.py`: every sample loads (both tracks).
- `tests/integration/test_sync1.py`: agent on 4 manifests with stub evidence/context (P1-S07).
- `tests/integration/test_pipeline_e2e.py`: full pipeline on the seed cases with LLM responses served from cache, so it runs offline and free (P2-S07).
- `tests/integration/test_no_hidden_leak.py`: all prompts of an F1 run contain no hidden test IDs/output (P2-S04).
- UI: Vitest on data mapping; one manual scripted walkthrough per sync recorded as a Synverk proof.

## Common integration risks
| Risk | Prevention |
|---|---|
| Field drift between tracks | Contract PR rule; sample-loading test on both sides |
| Paths differ between Windows laptops and containers | Use `pathlib`; contracts store repo-relative POSIX paths |
| Agent depends on sample quirks | Samples include one config, one code, one abstain case with realistic content |
| Live LLM in integration tests is slow/flaky | Tests run from the response cache; one separate smoke test hits the live API |
| Hidden tests visible to the agent | Hidden tests live outside the worktree; leak test is mandatory |
