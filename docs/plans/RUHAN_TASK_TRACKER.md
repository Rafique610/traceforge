# Track B task tracker (Ruhan-owned tasks)

**Status sync 2026-11-25. This file is authoritative for Ruhan's tasks; `RUHAN_AUDIT.md` is superseded by it.**

Source of truth for ownership: step documents under `docs/plans/phase-*/` ("Primary owner") and `TEAM_WORK_DISTRIBUTION.md` section 2.2.

## Status model
Each task records five separate facts: **IMPLEMENTED** (code exists), **TESTED** (automated tests pass), **INTEGRATED** (works with the other parts, incl. Rafique's), **REVIEWED** (Rafique reviewed the code), **APPROVED** (project owner approved). Then one overall label: COMPLETE & VERIFIED, IMPLEMENTED NOT VERIFIED, PARTIALLY COMPLETE, NOT STARTED, BLOCKED.

**Nothing is REVIEWED (Rafique's review of Ruhan's code is outstanding) and nothing is APPROVED (no owner approval is recorded), so no task is COMPLETE & VERIFIED.** In the table "I/T/G/R/A" = Implemented/Tested/Integrated/Reviewed/Approved: Y yes, P partial, N no.

**Ownership count (resolved 2026-11-25).** Ruhan has exactly **20** primary steps (the list in `TEAM_WORK_DISTRIBUTION.md` 2.2). Supporting only: P0-S05, P0-S06 Part B, P6-S04, and the P5-S16 label verification. Earlier "17", "22" and "23" figures were wrong. The team is two members (Rafique, Ruhan); Taha owns nothing.

## Evidence base (verified 2026-11-25)
Backend full suite 983 passed / 21 skipped (run before the 25 Nov changes). Targeted on 25 Nov: `tests/integration` 7 passed; reports 13; incidents 194; reviews 20; repair 64; `tests/agent` 339 (includes 17 RC2 and 3 hw_monitor); frontend vitest 12 files / 78 tests; `tsc -b` clean; `vite build` ok; oxlint warnings only; ruff clean. Docker: both images build (api 456 MB, web 74.1 MB); compose up healthy locally; migrations 0001/0002 applied; GET / and /api/health 200; POST returns 403 (showcase mode). actionlint passes on the workflow. NOT done: any GitHub Actions run, any live Investigate call against a real provider, any clean-clone dry run.

## The 20 primary steps
| Task | I/T/G/R/A | Overall label | Evidence | Remaining / human-only |
|---|---|---|---|---|
| P0-S03 Frontend scaffold | Y/Y/P/N/N | IMPLEMENTED NOT VERIFIED | vitest 12 files / 78 tests, `tsc -b`, `vite build` | Rafique review; owner approval |
| P0-S04 Proposal update + approval | P/N/N/N/N | PARTIALLY COMPLETE | Revised PDF dated 23 Nov at `D:\TraceForge\proposal\TraceForge_Assignment3_Proposal.pdf` and a GCR_Upload pack exist on disk (outside the repo). Supervisor evidence: the 18 Nov email (Akhtar Jamil, 10:41 AM) = conditional written permission to proceed after incorporating 13 changes (`D:\TraceForge\Assignment_3_TraceForge\Evidence\`); a noted verbal approval of the revised version is not a written document | Written confirmation of the revised proposal by the supervisor is not on disk (human-only); title registration and Rafique review of technical sections not evidenced |
| P1-S04 Incidents API + DB | Y/Y/P/N/N | IMPLEMENTED NOT VERIFIED | incidents 194 tests; Postgres migration and concurrency verified earlier; migrations 0001/0002 applied in compose | Rafique review; owner approval |
| P1-S05 Gateway, cache, ADR 0001 | Y/Y/P/N/N | PARTIALLY COMPLETE | gateway/BeatAPI/AxForge/budget tests; live smokes earlier | ADR 0001 stays PROPOSED (owner decides; see its evidence section) |
| P1-S06 Pipeline agent | Y/Y/P/N/N | IMPLEMENTED NOT VERIFIED | `tests/agent` 339 (fake gateway); live runs on 4 dev cases (L0) and the `results/final` RC1 runs | D20 budget is a placeholder; Rafique review |
| P1-S07 Sync 1 | Y/Y/P/N/N | IMPLEMENTED NOT VERIFIED | `tests/integration/test_sync1.py`: 7 passed (fake gateway; offline replay of `ManifestCaseSource`; route, pipeline, repair, report, review). The earlier "BLOCKED on P1-S03" is stale: P1-S03 is complete | Both members must run it on their own machines; Rafique review |
| P2-S04 Repair loop | Y/Y/P/N/N | IMPLEMENTED NOT VERIFIED | repair 64 tests (real git + real sandbox); `agent.e2e` CLI; migration 0002 | Rafique review of real-sandbox use |
| P2-S05 Report + review | Y/Y/P/N/N | IMPLEMENTED NOT VERIFIED | reports 13, reviews 20; hash-bound review, tamper returns 409. `missing_evidence` is now persisted as an audit event (type `missing_evidence`) and read by `reports/builder.py`; writing it into the INCONCLUSIVE payload would need an edit to the fingerprinted `agent/pipeline.py`, deliberately not done | Rafique review; owner approval |
| P2-S06 GitHub intake | Y/Y/N/N/N | IMPLEMENTED NOT VERIFIED | mocked intake tests; one earlier live intake on a public issue (pallets/flask#6190) | AS9 (issues repo) open; Rafique review |
| P3-S03 Reviewer UI | Y/Y/P/N/N | IMPLEMENTED NOT VERIFIED | vitest 78; ReviewPanel focus/ARIA fixes 25 Nov; FactorialView honest empty state; Investigate button now enabled (polling, accessible errors) | NOT verified against a live backend + real provider; Rafique review |
| P3-S04 Runner + results page | Y/Y/P/N/N | IMPLEMENTED NOT VERIFIED | runner, conditions, runs/report endpoints, results pages; `results/final` produced with it | Rafique review |
| P4-S01 A3 experiments | P/P/N/N/N | PARTIALLY COMPLETE | No A3-protocol run (L0 vs G0 on >=50 cases) exists. `results/final` (RC1, 35 sites; replicate counts r0=35 / r1=12 / r2=8 sites; 23 sites have r0 only; L1/G1 share diagnoses; the feedback mechanism was exercised in 1 case) is a REDUCED evaluation, not the A3 deliverable | OPEN DECISION (owner): supersede the A3 protocol with the reduced evaluation, or extend it. No claim that G1 beats anything |
| P4-S03 Demo + submission pack | P/N/N/N/N | PARTIALLY COMPLETE | `docs/demo/a3-demo.md` rewritten 25 Nov; pack on disk outside the repo | Dry run NOT done (needs both members); supervisor evidence is the 18 Nov conditional-permission email; written confirmation of the revised proposal still open (see P0-S04) |
| P5-S03 Full 2x2 x 3 replicates | P/P/N/N/N | PARTIALLY COMPLETE | Same reduced evaluation as P4-S01 (35 sites, not the full factorial with 3 replicates) | Same open decision. Key-1 ledger 152,664 tokens left; combined 742,728 left under the 4.8M ceiling |
| P5-S04 Model sensitivity (local) | P/P/N/N/N | PARTIALLY COMPLETE | Setup and monitor only. `agent/hw_monitor.py` (+3 tests). Ollama started locally; present: qwen3.5:4b-q4_K_M, medgemma:4b, all-minilm:22m (384-d embeddings work). `qwen2.5-coder:7b` is NOT installed (the step doc assumes it). One smoke (shop_api-001, G1, qwen3.5:4b, `--pipeline v5`, label EXPERIMENTAL-LOCAL-P5S04, `runs/e2e/p5s04-local-smoke-qwen35-4b`, 71 s) ended `provider_error` BadRequestError (HTTP 400 after 54 s; cause UNCONFIRMED: 4096 default context or tool/thinking format). Peaks: GPU 4763 of 6144 MiB, GPU util 22%, system RAM 15269 MiB of 16 GB | NO model-comparison result exists. No `G1_local` condition (Condition is a strict L0/G0/L1/G1 Literal; plan: run G1 via the e2e runner with `--provider ollama --model`, never mixed into the 2x2) |
| P5-S10 RC2 pipeline robustness | Y/Y/N/N/N | IMPLEMENTED NOT VERIFIED (opt-in, not validated) | New files `agent/rc2/{rationale,repeat_guard,config_check,version}.py`; `tests/agent/test_rc2.py` 17 passed; `results/rc2/rc2-fingerprint.txt` = `fe0b6000853d7ac8b5e070b8f53bfc02216dbc77575081944f10adc5e6784e75` (RC1 28 files + 5 RC2 files); RC1 fingerprint `ee3d8d87...56b51` re-verified UNCHANGED. Rationale truncation and repeat guard wired through a `chat_fn` wrapper `select_chat_fn("rc1"\|"rc2")`, default rc1; nothing calls it yet | Config-value checker is standalone (full wiring needs a hook in frozen `patch.py`/`feedback.py`: RC2 follow-up). NOT validated on dev or blind cases. Owner approval to use RC2 in any run still pending |
| P5-S11 Conditional hybrid experiment | N/N/N/N/N | NOT STARTED (conditional) | none | Conditional on P5-S08 go (Rafique) and owner spend approval |
| P5-S17 Regression-aware repair validation | N/N/N/N/N | NOT STARTED (conditional) | none | Needs P5-S10 validated, P5-S15, P5-S16 |
| P6-S02 CI + deployment | Y/P/N/N/N | PARTIALLY COMPLETE | `.github/workflows/ci.yml` (jobs: backend `pytest -m "not docker and not e2e"`, frontend `pnpm` vitest, contracts drift check incl. untracked files, docker); actionlint passes; both images build; compose healthy locally; ADR 0002 stays DRAFT | NO GitHub run has happened; no host (Q7), no public URL; branch protection is Rafique's. Frontend uses pnpm (`pnpm-lock.yaml`) but the dev machine has only npm. Step doc job names differ from CI (no security job or tests dir) |
| P6-S03 UI polish + audit view | Y/Y/P/N/N | IMPLEMENTED NOT VERIFIED | audit timeline, hit path, rating page, condition comparison; vitest 78 | Accessibility pass not signed off; statistics from P5-S02 for the full factorial view |

Counts by label: 11 IMPLEMENTED NOT VERIFIED, 7 PARTIALLY COMPLETE, 2 NOT STARTED, 0 COMPLETE & VERIFIED, 0 BLOCKED.

## Supporting (not counted in the 20)
| Task | Label | Evidence / remaining |
|---|---|---|
| P0-S05 Contracts (confirm) | INTEGRATION PENDING | Additive `AgentRunRecord` fields; schema regenerated; CI drift check; awaits Rafique review |
| P0-S06 Part B Model probe | IMPLEMENTED, PARTLY RUN | Local Qwen, Nemotron, AxForge smoke; no AxForge probe numbers, no Devstral or Mistral run |
| P6-S04 Paper | NOT STARTED | After P5 results |
| P5-S16 label verification | NOT STARTED | Ruhan independently verifies Rafique's hand-labelled relationships |

## Changes on 2026-11-25
1. `POST /incidents/{id}/investigate` (`backend/traceforge/investigation.py`): 202/404/409/422/503; background job `run_case_with_repair` + `save_outcome`; injectable factory. The default real-sandbox factory is UNTESTED live and needs `TRACEFORGE_MANIFEST` and a provider key, otherwise 503. Frontend Investigate button enabled. Not verified against a live backend with a real provider.
2. `missing_evidence` persisted as an audit event (see P2-S05).
3. `tests/integration/test_sync1.py` (7 tests).
4. RC2 opt-in files (see P5-S10); hw_monitor (see P5-S04).
5. CI workflow facts (see P6-S02).

## Historical sections below
Everything below is dated evidence from 21 to 23 Nov and is kept unchanged. Where it conflicts with the table above, the table wins (e.g. "28 repair tests" and "Vitest 65" are superseded by 64 and 78).

## Evidence from the 4-case live run (glm-5.3-flash, condition L0, 1 replicate, 22 Nov)
| Case | Gold | Result |
|---|---|---|
| shop_api-001 | configuration, `shop_api.REDIS_HOST` | cause class right (`REDIS_HOST`); patch rejected: it edited `lab/compose.yaml`, which the patch policy forbids |
| shop_api-002 | application code, `OrderItemIn.quantity` | exact target; patch verified in the sandbox, hidden tests passed (TEST_VERIFIED_IN_LAB) |
| shop_api-003 | runtime_dependency | correct, no patch |
| shop_api-004 | insufficient_evidence | correct abstention (`budget_exhausted`, 23.5k in / 7.7k out) |
This is a feasibility check, not a result: 4 cases, 1 replicate, 1 condition, no comparison.

## Bugs found and fixed during this run
- `git apply` input was newline-translated on Windows, so valid LF diffs failed to apply (`repair/worktree.py`; regression test added).
- A patch that failed to apply crashed the case instead of counting as a failed attempt (`repair/loop.py`; test added).

## AxForge token ledger
Persistent ledger `runs/axforge_usage.jsonl` (repo root, git-ignored). 15 live requests, 54,703 input + 12,274 output = 66,977 tokens, 2,333,023 left below the 2,400,000 ceiling. Provider-reported counts only. Free-versus-paid cannot be read from the API; the AxForge console is the authority.

## Update 23 Nov 2026: experiment infrastructure
- **Frozen dataset audit** (deterministic, read-only): 184 validated cases (151 test, 33 dev); freeze verified intact (manifest hash, content hash, lab base sha all match); case data complete. Open items found: runner used sample cases; evidence bundles and symptom text existed for 4 cases only; evidence collection regenerated the dataset per case (timeout); condition files pinned devstral/mistral; bare config keys did not match `service.KEY` gold; dev case shop_api-001 shares a variant group with test cases 020/040/139; configuration and code cases have no trace frames in their evidence (only outage cases do), so graph anchors rely on config binding.
- **Done in this update** (uncommitted): runner `--real` path (`evaluation/real_run.py`), provider/model as a run-level binding with `tier` (official = axforge glm-5.3-flash only), conditions default to axforge glm-5.3-flash, per-case artifact files, skip-without-record for cases lacking evidence (resumable), config-key qualification (`service.KEY`) with tool description, BeatAPI pacing counted from completion plus a separate development usage ledger, `evaluation.usage_report`, `results/` convention. Evidence collection speed-up and per-case symptom generation: see agent notes below.
