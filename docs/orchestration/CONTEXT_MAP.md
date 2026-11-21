# Context map (task → what to load)

Step docs live in `docs/plans/phase-*/`. Paths relative to repo root.

| Task | Required | Source to inspect | Restricted | Output | Validation |
|---|---|---|---|---|---|
| P0-S03 | step-03, invariants/frontend | health schemas | backend/** | frontend/ | `pnpm test`, build |
| P0-S04 | step-04, PROJECT_REQUIREMENTS, DECISIONS | proposal PDF (human supplies) | — | revised text + email draft | human sends; reply saved (EXTERNAL) |
| P0-S05 | step-05, INTEGRATION_PLAN | contracts/*, samples | contracts (change = own PR) | field-confirmation notes | samples validate |
| P0-S06-B | step-06, limits-report (branch rafique/P0-S06-retrieval-spike) | spikes/ | Part A | spikes/model_probe, report Part B | JSON from real calls |
| P1-S04 | step-04, ARCHITECTURE state machine, invariants/backend | health/, database.py | config, pyproject | incidents/** + migration | pytest, all transitions |
| P1-S05 | step-05, invariants/security+ml, free-provider research | config.py | — | agent/gateway,cache,call_log | mocked tests; Ollama smoke |
| P1-S06 | step-06, security invariants, contract samples | agent/ | sandbox, retrieval | agent pipeline | fake-gateway tests, injection test |
| P1-S07 | step-07 | manifests from Rafique P1-S03 | — | integration test | BLOCKED on P1-S03 |
| P2-S04 | step-04, security invariant | agent/, TestRun contract | sandbox | repair/** | no-leak, equal-attempts, policy tests |
| P2-S05 | step-05 | incidents/, repair/ | — | reports/, reviews/ | tamper test |
| P2-S06 | step-06 | incidents/ | — | github/** | mocked API tests |
| P3-S03 | P3 step-03, invariants/frontend | frontend/ | backend | UI | Vitest + walkthrough |
| P3-S04 | P3 step-04, invariants/ml | agent, repair | metrics | evaluation/runner, conditions | resume + freeze-guard tests |
| P4–P6 | their step docs | — | — | per step | real runs; mostly BLOCKED on Rafique/real data |
