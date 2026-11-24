# Ruhan audit: 20 assigned tasks against original acceptance criteria

> **SUPERSEDED by the status sync dated 2026-11-25.** This audit is a dated snapshot of 2026-11-21 and is kept unchanged below. Its statements that Rafique modules are absent, that no live model run exists, that P1-S07 is blocked, and its test counts (361 tests, 24 Vitest) are STALE. Current truth: `RUHAN_TASK_TRACKER.md` (five-fact status per task, 20 primary steps, nothing REVIEWED or APPROVED, nothing COMPLETE & VERIFIED).


Auditor pass, 2026-11-21, branch `ruhan/stage-b-work`. Read-only except this file. Criteria are quoted (shortened) from sections F/H/J of each step document and were not altered. RUHAN_CHECKLIST.md and DECISIONS.md were used as hints and checked against code.

Status codes: **V** VERIFIED by evidence, **IU** IMPLEMENTED-UNVERIFIED, **P** PARTIAL, **B** BLOCKED, **NS** NOT STARTED.
Evidence labels: **real-PG** real Postgres 16; **SQLite**; **fake-gw** fake gateway; **sample** JSON sample sources; **stand-in** the real-pytest-on-temp-git-repo runner in `tests/repair/gitrepo.py` (NOT Rafique's sandbox); **real-model** live local Ollama `qwen2.5-coder:7b` or OpenRouter `:free`. Anything marked *simulated* is not genuine end-to-end verification.

## 0. Global facts that cap many rows
- Rafique's modules are **absent from the tree**: no `sandbox/`, `evidence/`, `codeintel/`, `retrieval/`, `lab/`, `datasets/`, `evaluation/{metrics,baselines}`. Only `spikes/retrieval` (P0-S06 Part A) exists. So every real-evidence, real-sandbox, real-retrieval, frozen-dataset and metrics criterion is unmeetable today.
- No Devstral / Mistral run exists anywhere (no key, no free access; DECISIONS B7, B11). Every criterion written as "on Mistral" is unmet. Live model evidence is local Qwen 7B plus a few OpenRouter Nemotron `:free` calls (`backend/runs/llm_calls.jsonl`: 6 ollama cache hits, 2 ollama live, 4 nemotron live). No agent run, repair run or evaluation run has ever used a live model; all 133+ agent/repair/eval tests use fake-gw.
- Tests: `pytest --collect-only` = 361 tests; frontend 24 Vitest tests. I re-ran a targeted subset (174 tests, incl. `test_postgres.py`, migration test, real-correct/real-wrong patch, tamper-409, every-state-pair, resume) = **174 passed**, Postgres was reachable (not skipped).
- **Transient finding:** `backend/tests/repair/test_policy.py` (modified 19:27) currently has a `SyntaxError` at line 88 (unterminated string in `_VISIBLE`, a literal newline inside quotes). Collection of that file fails; another agent appears to be mid-edit. The D31 test-literal rows below rely on that file; re-run after it is fixed.
- Nothing is committed; no step is approved by the project owner or reviewed by Rafique (no PR exists), so no "merged after Rafique's review" criterion is met anywhere.
- Task-ID gaps: no `task gateway:probe`, no `task agent:run` live record, no repair CLI task, no `eval:report`.

---
## P0-S03 Frontend scaffold (TRAC-2). Task status: **IU**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Vite React-TS app with pnpm and lockfile | V | `frontend/package.json`, `pnpm-lock.yaml` present | none |
| Vitest + Testing Library configured | V | `frontend/src/test-setup.ts`; 24 tests across 6 files | none |
| Dev proxy to the API | IU | `frontend/vite.config.ts` | Never seen working against a live backend. Ruhan: `task dev` + `task web`, load the page. |
| `shared/api.ts` with error handling | IU | `frontend/src/shared/api.ts`; used by tests with mocked fetch | Ruhan: exercise a real failure. |
| HealthBadge with four states from the real response | IU | `health/HealthBadge.tsx` (5 tests, mocked fetch) | simulated (mocked responses); needs real backend run. |
| Tests for all four states | V | `health/HealthBadge.test.tsx` | none |
| Taskfile entries | V | `Taskfile.yml` `web`, `web:test`, `web:build` | none |
| README section | V | README `## Frontend` | none |
| Screenshots "API ok" and "API unreachable" on TRAC-2 | NS | no screenshots in repo | Ruhan: capture and attach on TRAC-2. |
| H: manual ok / degraded (stop db) / unreachable (stop API) | NS | no record | Ruhan: run the 3 manual cases. |
| H: status text only from response mapping | IU | unit tests assert mapped text | code read only; fine once manual run done. |
| J: merged after Rafique's review; both laptops, real backend | NS | no PR | Ruhan opens PR; Rafique reviews. |

## P0-S04 Proposal update and approval (TRAC-3). Task status: **B**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Team, model, hardware, four design fixes, three AI components, five safeguards, typo, AI-tool declaration (8 rows) | P | `docs/plans/phase-0-foundation/step-04-proposal-update-draft.md` is a text draft, not the revised PDF; proposal PDF is not in repo | Ruhan: obtain PDF, apply draft, produce revised PDF. |
| Cost recalculated with cited official price | NS | draft cannot cite a Devstral price (B11: no free access found) | Ruhan: check Mistral console, then cite. |
| Rafique reviewed technical accuracy | NS | no review | Rafique: review draft. |
| Every reference link still resolves | NS | not re-checked | Ruhan: re-check 13 URLs. |
| Email to supervisor (both CC), title registered, reply saved, TRAC-3 updated | NS | external | Audit-time row (21 Nov). Since then: 18 Nov supervisor email is on disk (conditional permission, Q3 ANSWERED-CONDITIONAL); written confirmation of the revised version, title registration still open. |
| Acceptance: supervisor reply approves or lists changes | NS | none | supervisor. |

## P0-S05 Contracts, supporting. Task status: **P**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| "Ruhan confirms the field list" | P | additive change made: `AgentRunRecord.provider` free-form, optional `replicate/temperature/seed/failure_reason` (B9); no recorded confirmation of the other four contracts | Ruhan: review `ContextBundle`, `EvidenceBundle`, `CaseManifest`, `TestRunResult` vs INTEGRATION_PLAN, post in PR. |
| "Ruhan confirms he can start Phase 1 from the samples" | V | Phase 1 built from samples; `tests/test_contract_samples.py` (6 tests) pass | state it in the PR. |
| Sample round-trip test; deliberately break a field -> test fails | IU | round-trip test exists; break-a-field experiment not recorded | Ruhan: do and log it. |
| 5-line stub consumer reads sample | V | `agent/sources.py` `SampleCaseSource` consumes samples | none |
| Both approve PR; TRAC-4 lists fields | NS | shared-contract change is uncommunicated | **Rafique must be told** (B9) and approve as a contract PR. |

## P0-S06 Part B Model probe. Task status: **P**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Read-limit curve for both models (100/300/1k/3k/6k lines x3) | P | `spikes/model_probe/results/read_limit.json`: Qwen 120/320/1,050 lines x3, real-model local | 3k and 6k NOT RUN; cloud model NOT RUN. Ruhan (needs larger-ctx machine or cloud key). |
| Write-limit and edit-validity numbers, both models | P | `write_limit.json` Qwen only, 5/20/50/100 x2 | cloud model NOT RUN. Ruhan. |
| Diff vs search/replace on 10 fixes | V | `format_comparison.json` (Qwen 10/10 vs 0/10) and `results_openrouter_nemotron/` (10/10 vs 4/10); real-model | Nemotron is not the planned model; Devstral not run. Qualifies as evidence for D19 only. |
| Free-tier limits measured from real calls | NS | only local latency (`rate_latency.json`); no cloud RPM/TPM/429 | Ruhan: measure on OpenRouter `:free` and Mistral Experiment if available. |
| Raw results saved; no invented numbers | V | raw JSON + `llm_calls.jsonl` saved | none |
| `limits-report.md` written with recommendations | V | `docs/research/limits-report.md` Part B with scope disclaimer | add Devstral rows later. |
| D19-D21 updated from provisional to decided | P | D19 supportable (search/replace 20/20 vs 4/20); D20 local-only (~4k tokens); D21 undecided | **supervisor/Ruhan decision** on D21; edit DECISIONS_AND_OPEN_QUESTIONS.md D19/D20 (not yet edited, doc is shared). |
| Each script reruns from clean clone with one task command | P | `task spike:probe PROVIDER= MODEL=` exists | not rerun from clean clone. |
| H(3): largest file size each model locates bugs in reliably | P | n=3 per size, no clean curve; Qwen only | needs n>=5 and second model. |

## P1-S04 Incidents API + DB (TRAC-8). Task status: **P** (mostly V; one gap)
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| ORM models, state enum + allowed map, guards | V | `incidents/{models,states,service}.py`; `test_allowed_map_covers_all_states_and_special_edges`, `test_guards_reject_and_write_nothing` | none |
| `transition()` with row lock and audit in one transaction | V | real-PG `tests/incidents/test_postgres.py::test_concurrent_transitions_only_one_wins_and_audit_is_exact` (re-run: pass) | none |
| Schemas with one-of validation | V | `test_create_schema_requires_case_or_symptom_and_service`, `test_create_validation_422` | unknown `case_id` -> 422 is **not** implemented (no manifest lookup); not in original F/H but noted by Ruhan. |
| Endpoints registered | V | `incidents/router.py`; `test_incidents_api.py` (6, SQLite) | none |
| Evidence persistence function | V | `repository.save_evidence_bundle`; `test_evidence_roundtrip_same_ev_id_across_incidents` | SQLite and PG JSONB covered. |
| Alembic migration reviewed and applied | V | `alembic/versions/0001_incidents.py`; up/down/up on real PG (docs claim; test re-run passes) | "applies on both laptops" unproven. |
| Tests: legal, illegal, guards, audit, pagination | V | `test_every_state_pair` (all pairs), `test_audit_is_append_only_in_repository_api`, `test_list_filter_and_pagination` | SQLite for most; PG for concurrency/JSONB only. |
| README | V | README `## Incidents API` | none |
| Manual `/docs`: create -> GET -> events show CREATED | IU | `test_create_get_events` covers it via TestClient | not done in browser; trivial. |
| Acceptance: move to VERIFIED without red/green -> 409, nothing written | V | `test_guards_reject_and_write_nothing`, `test_illegal_transition_maps_to_409_and_writes_nothing` | none |
| J: Rafique review, TRAC-8 approved | NS | no PR | Ruhan open PR; Rafique review. |

## P1-S05 Model gateway + ADR 0001 (TRAC-9). Task status: **P**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Settings for providers, keys (SecretStr), cache, rate, prices | V | `config.py` (ollama/openrouter/mistral/groq, SecretStr) | none |
| `ModelResponse` and `chat()`; rate limiter and retries | V | `agent/gateway.py`; `test_retry_on_429_then_success`, `test_gateway_error_after_max_retries` (mock transport) | 429 behaviour of a real provider not observed. |
| Disk cache keyed by canonical SHA-256 | V | `test_cache_miss_then_hit`, `test_key_stable_across_dict_order` | none |
| Call log without message content | V | `test_no_secret_or_content_in_logs` | none |
| Smoke test for Mistral, Ollama (Groq optional) | P | Ollama: real-model PASS then cache hit (`backend/runs/llm_calls.jsonl`: 2 live + 6 cache hits). OpenRouter `:free` Nemotron live (4 calls). **Mistral: NOT RUN** | Ruhan: Mistral key or free-access decision; else supervisor accepts substitution (DECISIONS B4/B7 are Ruhan's own, not supervisor-approved). |
| Mistral tool-call compatibility verified | NS | only Ollama (`tool_calls_from_text` adapter) | Ruhan after Mistral access. |
| ADR 0001 with exact model ID and limits | NS | `docs/adrs/` contains only 0002; no 0001 | Ruhan: write after D21 decision. |
| Unit tests (cache, retry, cost, key, no secret in logs) | V | `tests/agent/test_gateway.py` 14 tests | all mocked transport. |
| `.cache/` and `runs/` git-ignored | IU | not verified (repo has no .git in this tree) | Ruhan: check .gitignore. |
| README: set keys, run smoke | P | README Commands lists `llm:smoke`; key setup not checked in detail | Ruhan. |
| `task gateway:probe` reproduces P0-S06 numbers | NS | task absent; `spike:probe` is the substitute | Ruhan: add alias or amend by contract-change PR (do not edit criterion). |
| Cache key includes model ID and replicate index | V | `test_replicate_index_changes_key` | none |
| Acceptance: `llm:smoke PROVIDER=mistral` AND `ollama` pass; 2nd run `cache_hit=true` | P | ollama only | as above. |
| Acceptance: Q1 closed in DECISIONS_AND_OPEN_QUESTIONS.md | NS | Q1 still open (line 60) | Ruhan + supervisor. |

## P1-S06 Pipeline agent (TRAC-10). Task status: **IU**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Source protocols + sample implementations | V | `agent/sources.py` (`SampleCaseSource` etc.) | sample sources, not Rafique's. |
| Typed tools with validation and path restriction | IU | `agent/tools.py`; `test_invalid_tool_args_counted_and_recovered`, `test_hidden_tests_never_in_prompts` | fake-gw. |
| Versioned prompts and `prompt_hash` | V | `agent/prompts/*.md`; `test_prompt_hash_stable` | none |
| Diagnose loop with budget and terminal tool | IU | `diagnose.py` TOOL_BUDGET=6; `test_budget_exhaustion_abstains` | fake-gw; never run with a real model end to end. |
| Patch request for repairable classes only | IU | `test_abstain_makes_no_patch`, `test_runtime_dependency_no_patch_call` | fake-gw. |
| `run_case()` -> `AgentRunRecord`; incident states advanced | IU | `test_incident_states_advance`, `test_code_happy_path` | fake-gw + SQLite + sample evidence. |
| CLI task | IU | `Taskfile.yml agent:run`, `agent/run.py` | never run live. |
| Tests incl. prompt-injection sample | IU | `test_prompt_injection_does_not_change_tools_or_outcome` | fake-gw: proves the harness, not that a real model resists. |
| Works with Mistral and Ollama profiles | NS | no live agent run on either | Ruhan: live run on Ollama now; Mistral later. |
| Context budget from D20 enforced | P | `test_context_budget_enforced`; value 12,000 chars is a placeholder (limits report suggests ~16k chars/4k tokens for Qwen) | Ruhan: set from probe, make a Settings field. |
| Code-map tool in both retrieval arms | IU | `test_config_happy_path_and_code_map_tool_in_both_arms`; `get_neighbors` tool | sample context source; real code graph is Rafique's P2-S02 (absent). |
| H: live `task agent:run` on three samples with Mistral, records schema-valid | NS | none | Ruhan (Ollama first). |
| H: abstain and runtime_dependency samples -> no patch | IU | tests above | fake-gw only. |

## P1-S07 Sync 1 (TRAC-11). Task status: **B**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| `ManifestCaseSource` | NS | only `SampleCaseSource` exists | Ruhan: write once Rafique's manifest exists. |
| 4 cases run live on Mistral | B | no seed cases (P1-S03 absent), no Mistral | **Rafique** deliver P1-S03; Ruhan/supervisor for model. |
| Comparator path smoke-run on Ollama | NS | no seed cases | as above. |
| Mismatches triaged | NS | n/a | |
| Integration test replaying from cache (offline) | NS | n/a | Ruhan after live run. |
| Synverk proof; comment on TRAC-11 | NS | n/a | |
| H: 4 schema-valid records | NS | | |

## P2-S04 Repair loop (TRAC-15). Task status: **P**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Diff parser + policy with reasons | V | `repair/policy.py`; `tests/repair/test_policy.py` (7 tests; file currently broken, see section 0) | re-run after fix. |
| Worktree manager (create, apply, cleanup) | V | `repair/worktree.py`; `test_worktrees_cleaned_up` on real temp git repo | stand-in repo, not lab. |
| Baseline reproduction check | IU | `test_fault_not_reproduced` | simulated (stand-in runner). |
| Attempt loop with F0/F1 and early stop | IU | `test_equal_attempts_f0_f1`, `test_early_stop_on_visible_pass` | simulated (stand-in); model is fake-gw. |
| Hidden suite once, result never in prompts | IU | `test_no_hidden_leak_and_hidden_once`; `test_hidden_tests_never_in_prompts` | simulated; the structural guarantee needs re-test with Rafique's sandbox. |
| Patch freeze + SHA-256 | IU | `repair/loop.py`; report tests assert hash | stand-in. |
| `patches` and `validation_runs` tables + migration | V | `alembic/versions/0002_patches_validation_reviews.py`; `tests/reviews/test_migration.py`; PG migrations applied (status log) | none |
| State transitions with red/green payload | IU | `test_incident_states` (`test_repair_run.py`) | fake-gw/SQLite. |
| No-leak integration test | IU | as above | simulated. |
| Policy tests; equal-attempts test | V | `test_policy.py`, `test_equal_attempts_f0_f1` | within stand-in. |
| CLI task | NS | no repair CLI in `Taskfile.yml` | Ruhan. |
| Seed config + code results pasted on TRAC-15 | NS | no seed cases | Rafique P1-S03/S02. |
| Search/replace applier + diff conversion | V | `repair/edits.py`; `test_diff_roundtrip_and_signature_flag`; real-model 20/20 apply in probe | none |
| Size cap and test-file block | V | `test_path_rejections`, `test_oversize_binary_syntax` | none |
| Whole visible suite per attempt | IU | loop tests | simulated runner. |
| Signature-change flag | V | `test_diff_roundtrip_and_signature_flag` | none |
| Test-literal check unit test catches special-cased input | V | `test_test_literal_catches_special_cased_input`, `test_literal_special_case_rejected_in_loop` | known false-reject limitation (B10); re-run after file fix. |
| Acceptance: hand-correct patch verified, hand-wrong rejected by hidden suite | IU | `test_real_correct_patch_verified`, `test_real_wrong_patch_rejected_by_hidden` (re-run: pass) | **simulated**: real pytest in temp git repo, not Rafique's sandbox. Re-run on P1-S02 sandbox. |
| H: seed cases reach `TEST_VERIFIED_IN_LAB` or are explained | NS | none | Rafique + Ruhan Sync 2. |

## P2-S05 Report and review (TRAC-16). Task status: **IU**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| `Report` model and builder from DB records only | V | `reports/builder.py`; `test_report_code_never_touches_llm_or_network`, `test_report_is_deterministic` | none |
| Markdown renderer; endpoint JSON + MD | V | `reports/render.py`, `router.py`; `test_markdown_format`, `test_report_404_and_bad_format` | none |
| Review model + migration | V | `reviews/models.py`, 0002 migration; `test_alembic_offline_sql_creates_new_tables` | offline SQL + PG applied; migration down not shown. |
| Review service with hash check, state check, audit | V | `test_approve_matching_hash_201_closes_and_audits`, `test_wrong_state_409`, `test_second_review_409` | SQLite. |
| Review endpoint with constrained schema | V | `test_schema_constraints_422` | none |
| Tests: 4 outcome classes, tamper, wrong state, immutability | V | report tests for verified/unverified/runtime/insufficient; `test_tampered_hash_409_nothing_stored`; `test_reviews_patches_runs_are_immutable` | synthetic DB rows written by test helpers. |
| Impact list and signature flag shown | IU | `test_verified_report_has_patch_hash_impact_and_validation` | payload keys (`evidence_ids`, `missing_evidence`, patch impact) are written by test support; **the real pipeline does not yet write them**. Ruhan: wire pipeline. |
| Report for a seed case pasted on TRAC-16 | NS | no seed case | Rafique P1-S03. |
| Manual `/docs` GET report, POST review (201 / 409) | IU | covered by TestClient | not manual. |
| Acceptance: no LLM-generated field; every ID resolves | V | `test_report_code_never_touches_llm_or_network`, `test_every_id_resolves` | none |
| J: real seed-case report reviewed via API | NS | | needs a real seed case. |

## P2-S06 GitHub intake (TRAC-17). Task status: **IU**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Issues created for 2-3 seed symptoms | NS | none; AS9 (issues repo) open | Ruhan creates issues; decide AS9. |
| Settings with optional token and owner allowlist | V | `test_allowlist`, `test_default_settings_refuse_everything` | none |
| Strict URL parser | V | `test_parse_accepts`, `test_parse_rejects` | none |
| Client with timeouts and error mapping | V | `test_http_errors_no_incident`, `test_oversize_and_bad_json_502` | mocked HTTP. |
| Incident + untrusted evidence creation | V | `test_success_creates_incident_and_evidence`, `test_injection_text_is_stored_verbatim_as_data` | mocked HTTP. |
| Endpoint with schema | V | `github/router.py` `POST /incidents/from-github` | none |
| Tests (URL, mocked API, allowlist, injection-as-data) | V | `tests/github/test_github_intake.py` 15 tests | none |
| Real issue -> incident demonstrated; output on TRAC-17 | NS | live demo NOT RUN | Ruhan: allowlisted public issue, run once. |
| Acceptance: network off -> 502-style error, no incident | V | `test_network_failure_502_no_incident` | simulated network failure (mock). |

## P3-S03 Reviewer UI (TRAC-21). Task status: **IU**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Router and generated API types | P | `shared/router.ts`, `shared/types.ts` (hand-written? not generated from schema) | Ruhan: confirm generation or accept. |
| Incident list with filters | IU | `IncidentList.tsx` (4 tests, mocked) | simulated (mocked fetch). |
| Create from lab case / GitHub URL | IU | `NewIncident.tsx` (3 tests) | simulated; lab-case path has no lab. |
| Detail page sections 1-9; polling | P | `IncidentDetail.tsx` (4 tests); investigate endpoint pending (P2-S07) | polling cannot trigger a real investigation. |
| Diff viewer | V | `DiffView.test.tsx` (2) | none |
| Review panel with hash and 409 handling | IU | `ReviewPanel.test.tsx` (6) | mocked 409; backend 409 is separately tested. |
| Non-repairable outcome views | IU | detail tests | mocked. |
| Empty/loading/error states; Vitest tests | IU | 24 tests total | |
| impeccable UX pass; screenshots on TRAC-21 | NS | none | Ruhan. |
| H: manual walkthrough per class vs real backend | NS | none | needs real incidents of 4 classes (Rafique cases + Sync 2). |
| Acceptance: no hardcoded values; tampered path shows 409 | IU | tests with mocks | |

## P3-S04 Experiment runner + results page (TRAC-22). Task status: **P**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Condition files and loader | V | `evaluation/conditions/{G0,G1,L0,L1}.json`; `test_conditions_load_and_equal_budgets` | conditions name `devstral-small-latest`/`mistral`, which has never been called. |
| Runner with resume and freeze guard | IU | `test_resume_after_interrupt`, `test_freeze_guard`, `test_crash_recorded_and_run_continues` | simulated (fake pipeline, no manifest frozen by Rafique). |
| Run directory layout with meta; CLI task | V | `test_meta_records_and_listing`; `Taskfile.yml eval:run` | none |
| Runs list and report endpoints | P | `evaluation/router.py` has `/runs`, `/runs/{id}`, `/records`; no `/evaluation/report` | needs Rafique's metrics (P3-S02, absent). |
| Results page with breakdowns and n | NS | no results page in `frontend/src` | Ruhan after metrics. |
| Tests (guard, resume, conditions, page) | P | 6 backend tests; no page tests | |
| Dev-split run completed and resumed after manual interrupt | NS | no dev split (P3-S01 absent) | **Rafique** P3-S01; Ruhan run. |
| Acceptance: page numbers == `task eval:report` | NS | neither exists | **Rafique** P3-S02. |

## P4-S01 A3 experiments. Task status: **B**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Subset fixed by seed and committed; E1 on repairable test cases; rule baseline; L0 and G0 runs | B | no dataset, no retrieval, no metrics, no baseline, no model | **Rafique**: P3-S01, P3-S02, P2-S03, P2-S07. **Ruhan/supervisor**: model decision. |
| Report built, results committed; latency median/P95 and cost | B | none (gateway records latency/cost fields, unused) | after runs. |
| Tables + run IDs on TRAC-23 | NS | | |
| H: `eval:report` rerun identical on Rafique's laptop; one condition from cache with zero API calls | NS | cache mechanism unit-tested only | |
| Acceptance: each component n >= 50 | NS | | |

## P4-S03 Demo and submission pack. Task status: **B**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Demo script; demo cases from dev/reported cases | NS | none | after P3-S01. |
| Cached-response fallback prepared and disclosed | NS | gateway cache exists | Ruhan. |
| README complete for a fresh clone; clean-clone dry run on Rafique's laptop | P | README exists, no dry run | Rafique runs. |
| Two rehearsals; submission pack; self-evaluation; tag after explicit approval | NS | none | supervisor/project owner approves tag. |
| Acceptance: every segment works twice; both can show the code | NS | | |

## P5-S03 Full 2x2 x 3 replicates. Task status: **B**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Reuse-vs-rerun decision documented | NS | | Ruhan. |
| Replicate in cache key; first-run cache bypass | P | `test_replicate_index_changes_key`, `test_no_cache_forces_live_call` | unit-level only. |
| Parallel workers with isolated labs; shared rate limiter | NS | no lab, runner is sequential | Rafique lab + Ruhan runner. |
| Schedule posted; 12 cells complete; grid completeness check; replicate-difference check | B | needs P4 | |
| Acceptance: workers do not share lab state; same model ID/prompt hashes/dataset SHA | NS | | |

## P5-S04 Model sensitivity (local Qwen). Task status: **B**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| `G1_local` condition | P | `conditions/G1.json` exists (check it names local Qwen, not Devstral) | Ruhan: verify/repoint. |
| Same contexts reused; runs complete; hardware monitor; comparison table; hardware note; Q9 closed | B | needs P5-S03 G1 contexts | Ruhan after P5-S03. Probe's VRAM sampling script is reusable. |
| Acceptance: bundle hashes equal; table recomputes from saved runs | NS | | |

## P6-S02 CI and deployment (TRAC-30). Task status: **P**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| CI workflow with four jobs | IU | `.github/workflows/ci.yml` authored; never executed | Ruhan: push on a branch, observe. |
| CI required on `main` | NS | repo setting | **Rafique** (repo owner) enable branch protection. |
| Two-stage backend and frontend images | IU | `backend/Dockerfile`, `frontend/Dockerfile`, `nginx.conf`; images never built | Ruhan: `docker build`, record sizes. |
| Production compose | IU | `compose.prod.yaml`; not run | |
| Showcase mode | V | `showcase.py`; `tests/test_showcase.py` (3 tests: writes 403 when enabled) | none |
| Deployment ADR | P | `docs/adrs/0002-deployment.md` DRAFT; host open (Q7) | Ruhan/supervisor choose host. |
| Public link live; README updated | NS | none | |
| H: failing PR blocked, clean PR passes; image sizes recorded | NS | none | |

## P6-S03 UI polish + audit view (TRAC-31). Task status: **NS**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Audit timeline, hit path view, factorial view with CIs and n, impeccable pass, tests, screenshots, rating page bound to report hash | NS | none of these views in `frontend/src` (only incidents/review/health/shared) | Ruhan after P3-S03 live and P5-S02 `stats.json` (**Rafique**). |
| Acceptance: values match `stats.json` and audit events; keyboard-only flow | NS | | |

## P6-S04 Paper and pitch, supporting. Task status: **NS**
| Criterion | St | Evidence | Gap / who / next |
|---|---|---|---|
| Ruhan's sections drafted; pitch deck; usefulness study; threats to validity; AI-tool declaration; numbers linked to run IDs | NS | no paper sources in repo; `docs/research/` holds probe report only | Ruhan after P5 results; Rafique leads. |
| Acceptance: no unverified reference or unsourced number | NS | | |

---
## Unmet criteria: who acts and the exact next action
**Ruhan (can do now, no dependency):**
1. P0-S03: `task dev` + `task web`, capture ok/degraded/unreachable screenshots; attach to TRAC-2.
2. P0-S05: post field confirmation of the other four contracts; run the break-a-field check.
3. P1-S05: write `docs/adrs/0001-primary-model.md` (record that Devstral is untested); add `gateway:probe` alias; close or re-scope Q1.
4. P1-S06: live `task agent:run` on Ollama for the three samples; make D20 budget a Settings field set from probe (~16k chars for Qwen).
5. P2-S04/S05: add repair CLI task; make the pipeline write `evidence_ids`, `missing_evidence`, patch impact; fix `tests/repair/test_policy.py` syntax error (if not already fixed by its author) and re-run.
6. P2-S06: create 2-3 issues, settle AS9, run one live intake.
7. P6-S02: build both images, run CI on a pushed branch, pick host (Q7).
8. P1-S04: decide whether unknown `case_id` -> 422 is wanted (needs manifest lookup; blocked on Rafique's manifest).

**Rafique (blocking):** P1-S02 sandbox (re-verify P2-S04 on a real sandbox), P1-S03 seed cases (unblocks P1-S07, P2-S04 seed results, P2-S05 real report, P3-S03 walkthrough), P2-S01..S03 evidence/graph/retrieval, P2-S07 Sync 2, P3-S01 frozen dataset, P3-S02 metrics and `eval:report`, P5-S02 stats. Also: be told of the `AgentRunRecord` change (B9), review every Track B PR, enable CI-required branch protection.

**Supervisor / project owner:** Q3 (ANSWERED-CONDITIONAL by the 18 Nov email; written confirmation of the revised scope still open, P0-S04); decision on D21 and on whether Devstral is required or an OpenRouter `:free` / local model may be primary (DECISIONS B4/B7/B11 are unratified); approval of any step (AGENTS.md) and of the `a4-submission` tag.

## Summary
Task-level counts (20 tasks); the review-duty line is not counted.

| Status | Count | Tasks |
|---|---|---|
| VERIFIED (all rows) | 0 | none (no PR, no Rafique review; P1-S04 is closest) |
| IMPLEMENTED-UNVERIFIED | 5 | P0-S03, P1-S06, P2-S05, P2-S06, P3-S03 |
| PARTIAL | 7 | P0-S05, P0-S06-B, P1-S04, P1-S05, P2-S04, P3-S04, P6-S02 |
| BLOCKED | 6 | P0-S04, P1-S07, P4-S01, P4-S03, P5-S03, P5-S04 |
| NOT STARTED | 2 | P6-S03, P6-S04 |
| Total | 20 | |

Simulation caveats that apply even to V/IU rows: all agent, repair, pipeline and runner tests use a fake gateway and sample/stand-in sources; only incidents concurrency/JSONB, migrations, the gateway live smoke (Ollama, OpenRouter `:free`) and the model probe touch a real Postgres or a real model. No row touches Rafique's sandbox, evidence, retrieval or dataset, and no row touches Devstral/Mistral.


---
## Addendum — evidence added after the audit above (2026-11-21, later the same day)
Criteria are unchanged. Labels as above. "real" = no fake gateway/stand-in for that item.

| Item | New evidence | Kind | Effect |
|---|---|---|---|
| P0-S03 manual checks + screenshots | `docs/screenshots/badge-{ok,degraded,unreachable}.png`, `ui-list.png`, `ui-detail.png`, `ui-new-incident.png` from headless Chrome against the real API + Postgres + Vite proxy; degraded = db container stopped, unreachable = API stopped | **real** (API, DB, UI) | closes "screenshots" and "manual ok/degraded/unreachable"; the dev proxy criterion is now seen working. Still needs Rafique review (no PR). |
| UI defect found | undiagnosed incident displayed "SUPPORTED"; fixed (`NOT_DIAGNOSED`), test `test_incident_without_diagnosis_is_not_reported_as_supported`, UI wording | real walkthrough | P2-S05/P3-S03 quality gain |
| P2-S06 live intake | real public issue `pallets/flask#6190` → incident in real Postgres, evidence `EV-0001` untrusted, events `['created']`; disallowed owner → 422 | **real** (GitHub API, Postgres) | closes "real issue → incident demonstrated". Not covered: network-off live case (mocked only). |
| P6-S02 images | `traceforge-api:local` 334 MB and `traceforge-web:local` 74 MB built; API container runs uid 10001 and returned `{"status":"ok","db":"up"}` against the real Postgres; web container served the UI (HTTP 200) and proxied `/api/health` to the API on a shared network | **real** builds/containers | closes "two-stage images" and image-size record. NOT RUN: CI workflow on GitHub, `compose.prod.yaml` stack, public deployment. |
| P1-S06 / P1-S05 live model | Local `qwen2.5-coder-7b-ctx16k` and OpenRouter `nvidia/nemotron-3-ultra-550b-a55b:free` (experimental) ran `agent.run` on the 3 sample cases (condition G0, 1 run each, **sample evidence sources, no sandbox**): Qwen → config REDIS_HOST correct + patch produced; code case wrongly abstained (`model_output_malformed`); abstain case correct. Nemotron → config REDIS_HOST, code `orders.py::order_total`, abstain case abstained but with 3 invalid tool calls. | **real model, sample sources** | satisfies "live run on samples" in a limited sense; NOT Mistral/Devstral; n=3, one run. |
| Real-model bug found | reasoning model hit `finish_reason=length` at 1024 tokens → empty patch reply reported as `no_edit`; fixed (`llm_max_output_tokens=4096`, `OutputTruncated`, `output_truncated` failure reason) + test | real model | gateway robustness |
| P2-S04 test-literal check | D31 rule rewritten (AST special-position rule); 14-case table: 0 false positives / 0 false negatives; natural `/ 100` fix now passes through the stand-in runner | stand-in | known limitation resolved for the common case; bypassable by computed literals (documented) |
| P3-S04 results page | `#/evaluation` list/detail pages + `GET /evaluation/runs/{id}/records`; 29 frontend tests, 7 evaluation tests; shows raw counts only | simulated data (fixture runs) | page built; computed-metrics view waits for Rafique's P3-S02; no screenshot with real runs yet |
| ADR 0001 | `docs/adrs/0001-primary-model.md` (PROPOSED) | doc | exists; cannot be finalised until Q1 closes |
| Gateway safety | Ollama `-cloud` models refused unless `TRACEFORGE_LLM_ALLOW_OLLAMA_CLOUD=true`; tests | real guard | B12 |

### Task status after the addendum
Still **0 tasks "Verified complete"** under the step documents' definition of done (each requires the project owner's approval and Rafique's review, and several need Rafique's modules or Devstral). Strongest: P0-S03, P1-S04, P2-S06 now have real-environment evidence for all technical criteria; they await review/approval. Unchanged blockers: P0-S04 (PDF, supervisor), P1-S07, P4-*, P5-* (Rafique, dataset, Devstral), P6-S03/S04 (depend on P5).


---
## Addendum 2 — real end-to-end evidence (2026-11-21, evening)
All items below used REAL components: real lab (Docker), real evidence collector (read-only proxy), real retrieval + graph, real sandbox containers, real Postgres incident DB, local Ollama model `qwen2.5-coder-7b-ctx16k`. Nothing was patched into lab/ or datasets/ (disposable worktrees only).
| Case | Class (gold) | Model diagnosis | Outcome | Why |
|---|---|---|---|---|
| shop_api-001 (G0,L0,G1,L1) | configuration | abstained | NO_PATCH | tool budget exhausted (6 read_evidence calls, no submit) |
| shop_api-002 (4 conds) | application_code | wrong (configuration, settings.db_host) | REJECTED | 3 edits did not match file |
| shop_api-003 (G0) | runtime_dependency | configuration REDIS_HOST (wrong) | UNVERIFIED | reproducer passes on unmutated tree |
| shop_api-004 (G0) | insufficient_evidence | configuration (wrong) | UNVERIFIED | same |
Metrics (real records, dataset sha 929c4ab8…): cause-class accuracy 0/4 (G0) for the 7B model; the rule baseline scores 2/4. E1 on real evidence: all retrieval methods ≈0 (evidence has no trace frames), L ≡ G (identical prompts) — the graph factor cannot be assessed until the evidence contains traces.
Pipeline findings fixed: tool-call history format imitated by the 7B model (diagnose.py), report mislabelled misdiagnoses as "verified" (reports/builder.py + test), `e2e` marker registered. Open: lab hides faults (no tracebacks) — fix in progress; report fields `symptom_evidence_ids`/`missing_evidence` not written by the pipeline.
What this verifies: the integrated pipeline runs end to end with the real sandbox/evidence/retrieval and persists to the real DB, report endpoint shows REVIEW_PENDING with evidence/hypotheses/usage, human approval remains required. What it does NOT verify: a model producing a patch that passes hidden tests (no run reached that), the F0/F1 and G/L effects.
