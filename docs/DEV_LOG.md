# TraceForge development log (concise; coordinator-maintained)

Strategy: BUILD -> IMPROVE -> INTEGRATE -> STABILIZE -> FINAL EVALUATION -> FINISH. No new mini-experiments. Model calls only when real model behaviour must be evaluated. No commits/pushes without the owner's permission.

## Status (24 Nov 2026)
- Done earlier (dev-d1 / pipeline v5, development track): symptom pipeline, labelled evidence, symptom-aware lexical + graph retrieval, diagnosis v2 + claim validation, discovery tools, tool-budget fix, target handoff + patch scope policy, shared AxForge 30 s pacing + 429 handling, run isolation/binding, frozen-artifact manifest, patch-from-saved-diagnosis mode. Dev-split results: diagnosis 12/12, patches 12/12 verified (Level 1 only; one sample).
- Tests at last full run: 842 passed, 23 skipped; Ruff clean. AxForge ledger 1,163,572 committed (ceiling 2.4M; 600k reserve beyond it).

## Workstreams and file ownership (shared tree; no worktrees: they would drop uncommitted work)
| Owner | Scope (edit only here) |
|---|---|
| Backend agent | incidents, reviews, reports, ratings, github, health, main/config/database, alembic + their tests: approval/hash-bound integrity, state machine, logging, validation, migrations |
| AI-pipeline agent | evidence, retrieval, codeintel, new diagnostics package, agent/{diagnose,tools,prompting,evidence_view,symptom,sources,lab_collect}, diagnose_v2 prompt: deterministic findings, config-fault path, abstention |
| Repair agent | repair/, sandbox/, agent/{patch,repair_run,handoff,real_sources}, patch_v5 prompt: feedback provenance + guard v2, iterative repair, scope edge cases, sandbox robustness |
| Frontend agent | frontend/ only: API contract check, workflows, error states, new diagnosis fields, accessibility |
| Coordinator (me) | agent/pipeline.py, agent/e2e.py, agent/gateway.py/axforge.py/beatapi.py (provider safety), evaluation/*, scripts/, docs, full-suite/Docker/integration runs, release freeze |
Rules: agents run targeted tests only (one pytest at a time), no Docker/full suite/servers, and NO model or provider calls. The shared AxForge limiter (30 s start-to-start, one request in flight, machine-wide) is the only way requests are sent.

## Coordinator changes so far
- `agent/e2e.py` (the CLI that persists a real run to the incident DB for the UI) now runs pipeline v5 by default (`--pipeline v4` keeps the formal one): symptom from visible tests (no gold terms), live requests, AxForge billing gate required (`--axforge-billing-verified`), `symptom.json` saved.

## Known issues / backlog (priority)
1. [agents running] approval hash binding + API robustness; config-fault diagnosis + deterministic findings; feedback provenance/guard v2 + iterative repair; frontend contract + workflows.
2. API has no endpoint that runs the agent on an incident (the agent runs via CLI and persists to the DB). Decision: do NOT add a provider-calling API path now (spend/safety); the UI reviews runs the CLI produced. Revisit only if the owner wants it.
3. Integration pending: full suite, Postgres migrations (`alembic upgrade head`, `alembic check`) on a clean DB, Docker compose (dev and prod), frontend build + tests, end-to-end workflow, security checks.
4. Final evaluation scale problem (needs the owner's decision at plan time): the formal design is 151 test cases x 4 conditions x 3 replicates = 1,812 case-runs. Measured v5 cost is about 16.5k tokens (diagnosis) + about 4k (patch attempt) per case-run, so the full design is about 36M tokens; the budget left to the 2.4M ceiling is about 1.24M. Sharing one diagnosis between L0/L1 and between G0/G1 (feedback only matters after a failed first patch) cuts it to about 6M per replicate and still does not fit. About 60 diagnosis+patch units fit (about 30 cases x 2 arms x 1 replicate). Options will be laid out in the consolidated plan (stratified subset, one replicate, allowance reset window, BeatAPI replicates as a separate experiment).
5. Formal-pipeline question for the plan: the final evaluation presumably uses the frozen v5 pipeline as the formal one (v4 results stay historical). Needs explicit owner approval.


## Milestone 1 (24 Nov 2026): four parallel workstreams merged
- **Backend:** review/approval re-hashes the stored diff against the frozen hash (409 on mismatch), refuses approving a patch that never reached VERIFIED; symptom redaction; request-id + access-log middleware, 1 MB body cap, generic 500 handler; CORS + fail-fast config validation; Alembic head vs ORM drift test (no drift). `EvidenceItemOut` exposes derived `scope/basis/origin`.
- **AI pipeline:** new `diagnostics/` (9 generic hint rules: container down, unresolvable hostname vs compose + settings default, startup validation errors, import/syntax errors, negated/power-of-ten symptom values, implausible defaults, queue-name mismatch, "nothing observed" abstention hint) appended as FINDING items; G-only `symptom_config` anchors (settings read by the failing handler/test and its callees); collector robustness (unavailable containers/logs become explicit items; unparseable settings file; clipped log lines); tools validation tightened. Offline on 15 dev config cases the gold settings chunk is in the packed context for G 15/15 (was 5) and L 12/15 (was 5); code cases G 11/11, L unchanged.
- **Repair:** `FeedbackItem` (visible-only provenance; hidden runs rejected structurally), feedback shows per-test assertion lines, F1 attempt N also sees a summary of the previous edit; guard v2 (hidden-only names blocked everywhere; shared names only in feedback/symptom/finding spans, the model's own words and the diagnosis lines; assert-fragment detection report-only); frozen patch cannot be reassigned after the hidden run; import-line insertions allowed by the scope policy; JSON/TOML/YAML syntax check; sandbox errors become UNVERIFIED sandbox_error with detail.
- **Frontend:** contract matched the backend (no mismatches); provenance tags, diagnosis dev fields, rater-name validation; 69 vitest tests, typecheck and build pass.
- **Coordinator fixes found at integration:** guard v2 was too strict for the real flow (a shared test name in the diagnosis rationale, in the model's own tool-loop messages or in a FINDING item would have crashed real runs) -> allowed those spans and added tests; `no_failure` symptoms now also get findings/abstention hint; run records carry feedback provenance and guard fragment hits; e2e CLI runs v5.
- **Open:** Postgres migration check, Docker compose, e2e workflow, security pass, full-suite confirmation (running), model-level validation of the new diagnostics/config path on dev config cases (the only place real model calls are justified before freeze).


## Milestone 2: integration, stabilization, RC1 (24 Nov 2026)
- Integration found and fixed: API container did not migrate (clean DB had no tables) -> Dockerfile CMD runs `alembic upgrade head` first; guard v2 false positives on real prompts; run records now carry feedback provenance + fragment hits; v5 config-key canonicalisation (upper-case `service.KEY`); `no_failure` symptoms get findings.
- Verified: backend 916 passed / 21 skipped, Ruff clean; frontend 69 tests + build; Alembic upgrade/check/downgrade on clean Postgres; prod compose (db/api/web) healthy; write workflows on Postgres.
- Pre-freeze model check (3 dev config sites, L0, ~92k tokens): diagnosis 3/3 right key, patches 2/3 verified; the failure is a genuine feedback opportunity.
- RC1 fingerprint `c74da597...d796b35` (28 files). Final evaluation plan written (`docs/research/final-evaluation-plan.md`): the formal design (151 cases x 4 x 3) is about 30x over the token budget; option A (18-case stratified subset, 1 replicate) needs the owner's approval. ~1.14M tokens left to the ceiling.


## Milestone 3: final evaluation executed (24 Nov 2026)
- Ceiling raised to the full 3M allowance by owner authorization; final-eval mode (`--final-rc1`, selection + fingerprint gate), staged replicates (`--replicate-start`), shared-diagnosis patch runs (`--share-diagnosis`, abstentions reproduced without model calls), `scripts/final_eval.sh`, report tool `evaluation/final_report.py` (agent).
- Evaluation done on key 1 (see `docs/research/final-evaluation-report.md`). Key-1 allowance left: 152,664.
- In progress: second-key support + job scheduler (agent), then live verification of key 2 (minimal requests) and a proposal for approval.


## Milestone 4: second key and documentation (24 Nov 2026)
- Second AxForge key slot (`AXFORGE_API_KEY2`) with its own ledger, pacing file, halt state and 3M ceiling; 4.8M combined ceiling; enabled only by `runs/axforge_keys_verified.json`. Job-level scheduler (`evaluation/scheduler.py`, `scripts/parallel_eval.py`): one job per slot, halt on first failure, no auto retry, failover only of pending work.
- Verified: both keys authenticate to `glm-5.3-flash`; a simultaneous start gave no 429. Quota independence of key 2 is owner-stated, not provable via the API. Ledger shows key 1 at 2,847,367 of 3,000,000; the dashboard figure is unknown until the owner supplies it.
- Docs added: README update, `docs/ARCHITECTURE.md`, `docs/research/dual-key-operations.md`.

## 25 Nov 2026: root-cause / impact / regression design and plan tasks (docs only)
- Added design `docs/research/root-cause-impact-regression-design.md` and PROPOSED tasks P5-S12 to P5-S17 (step docs, plans, handoff, risks, decisions D37/AS12/Q17/Q18, requirement ER-09, ADR 0003 addendum, PROPOSED architecture sections). All NOT STARTED, pending owner approval. No code, no model requests, no frozen artifact touched; RC1 unchanged.

## 25 Nov 2026: Ruhan status sync, Investigate route, RC2 opt-in, local-model smoke
- **Docs:** every Ruhan-task document now uses the five-fact model (implemented / tested / integrated / reviewed / approved) plus one label; nothing is reviewed or approved, so nothing is COMPLETE & VERIFIED. Ruhan has exactly 20 primary steps (earlier 22/23 were wrong). Correction notes added to the evaluation docs: replicate coverage is 35/12/8 sites (not "12 sites with replicates 0 to 2"); no result changed. `docs/demo/a3-demo.md` rewritten (two presenters; dry run NOT done).
- **Code (see tracker for evidence):** `POST /incidents/{id}/investigate` (202/404/409/422/503; background `run_case_with_repair` + `save_outcome`; needs `TRACEFORGE_MANIFEST` and a provider key; default real-sandbox factory untested live); Investigate button enabled; ReviewPanel focus/ARIA fixes; FactorialView honest empty state; `missing_evidence` persisted as an audit event; `tests/integration/test_sync1.py` (7 tests); RC2 opt-in files `agent/rc2/*` (17 tests; fingerprint `fe0b6000853d7ac8b5e070b8f53bfc02216dbc77575081944f10adc5e6784e75`; RC1 `ee3d8d87...` unchanged; not validated; nothing calls `select_chat_fn` yet); `agent/hw_monitor.py` (3 tests).
- **Local models (P5-S04):** Ollama started locally; qwen3.5:4b-q4_K_M, medgemma:4b, all-minilm:22m present; `qwen2.5-coder:7b` not installed. One smoke (shop_api-001, G1, qwen3.5:4b, v5) ended `provider_error` BadRequestError (HTTP 400 after 54 s, cause unconfirmed). Peaks: GPU 4763 of 6144 MiB, RAM 15269 MiB of 16 GB. No model-comparison result exists.
- **CI/Docker:** workflow authored, actionlint passes; both images build (456 MB, 74.1 MB); compose healthy locally. No GitHub run, no host, no public URL.
- **Tests:** backend 983 passed / 21 skipped (before today's changes); targeted suites and vitest 78 as in `RUHAN_TASK_TRACKER.md`.
- **Tokens:** Key-1 152,664 left; combined 742,728 left under the 4.8M ceiling.
- **Not established:** any G1 or graph superiority; A3-protocol completion (open owner decision).

