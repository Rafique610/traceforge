# Phase 1 — Core components

**Status:** NOT STARTED

## Phase information
- **Purpose:** build the foundation pieces of both lanes in parallel: the victim lab, the sandbox and first labelled cases (Track A); the incident API, LLM gateway and pipeline agent (Track B).
- **Objectives:** a healthy lab with documented contracts; a locked-down test runner; 4 validated seed cases (one per outcome class); incidents with a guarded lifecycle; a cached, logged LLM gateway with a pinned primary model; an agent that diagnoses sample inputs.
- **Scope:** no real evidence collection, graph or retrieval yet (Phase 2); the agent works on contract samples.
- **Expected outcome:** milestone **M1 (Sync 1)**: the agent produces valid records on the 4 real seed cases.
- **Prerequisites:** Phase 0 complete (M0).

## Task overview
| Step ID | Task | Responsible | Dependencies | Status |
|---|---|---|---|---|
| [P1-S01](step-01-lab-fixtures.md) | Lab fixtures (TRAC-5) | Rafique | P0-S02 | NOT STARTED |
| [P1-S02](step-02-sandbox-test-runner.md) | Sandbox test runner (TRAC-6) | Rafique | P0-S05 | NOT STARTED |
| [P1-S03](step-03-fault-generator-and-seed-cases.md) | Fault generator + 4 seed cases (TRAC-7) | Rafique | P1-S01, P1-S02 | NOT STARTED |
| [P1-S04](step-04-incidents-api-and-database.md) | Incidents API + DB (TRAC-8) | Ruhan | P0-S05 | NOT STARTED |
| [P1-S05](step-05-model-gateway.md) | Model gateway + cache + ADR (TRAC-9) | Ruhan | P0-S02 | NOT STARTED |
| [P1-S06](step-06-pipeline-agent.md) | Pipeline agent (TRAC-10) | Ruhan | P1-S04, P1-S05 | NOT STARTED |
| [P1-S07](step-07-sync-1-agent-on-seed-cases.md) | Sync 1 (TRAC-11) | Ruhan (+Rafique) | P1-S03, P1-S06 | NOT STARTED |

## Execution order
- **Track A (sequential):** P1-S01 → P1-S02 → P1-S03. P1-S02 can start in parallel with P1-S01 once contracts merge (it can test on a tiny throwaway package), but P1-S03 needs both.
- **Track B:** P1-S05 can start right after P0-S02; P1-S04 after P0-S05; P1-S06 after both.
- **Join:** P1-S07 needs P1-S03 and P1-S06.
- Blocking: P1-S02 also blocks P2-S04 (repair loop); P1-S01 blocks P2-S01 and P2-S02.

## Deliverables
`lab/` with two services, contracts, tests and probes; `backend/traceforge/sandbox/`; `datasets/` generator + 4 manifests + hidden tests; `backend/traceforge/incidents/` + migration; `backend/traceforge/agent/` gateway, cache, pipeline, prompts; `docs/adrs/0001-primary-model.md`.

## Completion criteria
- [ ] `task lab:up` healthy and `task lab:test` green on both laptops
- [ ] `task sandbox:selftest` passes (pass/fail/timeout/no-network)
- [ ] `task dataset:validate` passes for 4 seed cases
- [ ] Incidents create/read and illegal transitions rejected
- [ ] Gateway smoke test passes on Mistral and Ollama; cached rerun makes 0 API calls
- [ ] ADR 0001 merged with model ID and free-tier limits
- [ ] 4 schema-valid `AgentRunRecord`s from real seed cases (Sync 1)

## Handoff to Phase 2
- Rafique → Ruhan: `run_tests()` usage and timings; manifest location; how hidden tests are mounted.
- Ruhan → Rafique: the agent's evidence/context access functions (what fields it actually uses), so P2-S01/P2-S03 produce what matters.
- Both: any contract changes made at Sync 1.

## Navigation
- [P1-S01 Lab fixtures](step-01-lab-fixtures.md)
- [P1-S02 Sandbox test runner](step-02-sandbox-test-runner.md)
- [P1-S03 Fault generator and seed cases](step-03-fault-generator-and-seed-cases.md)
- [P1-S04 Incidents API and database](step-04-incidents-api-and-database.md)
- [P1-S05 Model gateway](step-05-model-gateway.md)
- [P1-S06 Pipeline agent](step-06-pipeline-agent.md)
- [P1-S07 Sync 1](step-07-sync-1-agent-on-seed-cases.md)
- Previous: [Phase 0](../phase-0-foundation/README.md) · Next: [Phase 2](../phase-2-evidence-to-repair/README.md) · [Plans README](../README.md)
