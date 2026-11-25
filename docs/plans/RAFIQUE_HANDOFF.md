# Rafique handoff: what exists, what remains (audit of 2026-11-22)

Evidence: `git log` (authors `Rafique610` vs `ruhank-dev`), `main` at 45e669d, the code, and test runs on 2026-11-22. Docker was not running during this audit, so Docker-dependent checks (sandbox containers, live evidence proxy, lab stack) were NOT re-run today; their status below comes from the earlier live verification recorded in `DEPENDENCY_MAP_RAFIQUE.md` section D. Nothing here is "Verified complete": only the project owner approves a step.

## 1. Rafique's own completed work (his commits)
| Item | Evidence |
|---|---|
| P0-S01 repo setup | commits c9902a1, c7e2bce, .gitattributes; Ruhan's clone/collaborator step still open |
| P0-S02 backend scaffold | commit 4a4a4df (FastAPI app, config, health); his branch is merged to `main` |
| P0-S05 shared contracts | commits 4a4a4df, 29f8a93 (`log_format` on `CaseManifest`); samples + JSON schemas in `backend/traceforge/contracts/`. NEEDS REVIEW: Ruhan's additive `AgentRunRecord` change (aa2ac9a) |
| P0-S06 Part A retrieval spike | commit 0805e6b: `spikes/retrieval/`, `docs/research/limits-report.md` Part A |
| Plan, step docs, process rules | docs commits 19-21 Nov |

## 2. Track A components that exist but were written by the Claude-assisted session for Ruhan (commits aa2ac9a, 996f004, author `ruhank-dev`)
These are Rafique's tasks by ownership. He did NOT write them and has not reviewed them. He should review and extend them, not rebuild them.
| Task | State on `main` | Verified how (and limits) |
|---|---|---|
| P1-S01 Lab (`lab/`: shop_api, worker, compose) | implemented | earlier live stack run; a realism fix (silent failure handling) was in progress; not re-run today |
| P1-S02 Sandbox (`backend/traceforge/sandbox/`) | implemented | 7 tests pass today; 12 Docker tests skipped today (earlier: all passed in real containers); worker-service tests not runnable |
| P1-S03 Fault generator + seed cases (`datasets/`, `backend/traceforge/faultgen/`) | partial: 4 dev cases (`shop_api-001..004`), `manifests/dev.json` | 21 faultgen tests pass, 2 skipped (Docker); 4 cases validated 3x earlier; distances set by hand; far below the target of at least 144 frozen + 30 dev |
| P2-S01 Evidence collector (`evidence/`) | implemented | 46 tests pass, 21 skipped (need the docker proxy); earlier live run: 18/18 writes refused, no secret leaks. Gaps: no CLI, case 004 suppressed-logs hint not honoured, health probe timeouts |
| P2-S02 Code graph (`codeintel/`) | implemented | 26 tests pass; call-resolution precision not measured |
| P2-S03 Retrieval L and G (`retrieval/`) | implemented | 24 tests pass; E1 benchmark on real evidence is not meaningful yet (2 cases, all methods near 0) |
| P3-S02 Metrics + baseline (`evaluation/`) | implemented | 25 tests pass; run only on 10 hand-made/real records; edit-quality metrics missing |

## 3. Work of Ruhan's that overlaps and should be reused
`docker compose` lab + Taskfile targets, `docs/plans/DEPENDENCY_MAP_RAFIQUE.md`, `docs/orchestration/DECISIONS.md` (B9, B13 contract changes), the RULES baseline record type, `AgentRunRecord` new optional fields (`replicate`, `temperature`, `seed`, `failure_reason`), the pipeline/repair/report code that consumes the above.

## 4. Outstanding for Rafique, dependency-first
| # | Task | What he delivers | Reuse | Remaining | Ruhan tasks waiting | Blocks or parallel |
|---|---|---|---|---|---|---|
| 1 | Review of the Track A code above and the `AgentRunRecord` change (P0-S05) | written review/approval or change requests | all of section 2 | read, run `task` checks with Docker up, list changes | everything that touches real components (P1-S07, P2-S04 integration, P3-S04) | blocks sign-off, parallel to coding |
| 2 | P1-S03 seed cases and P3-S01 frozen dataset | at least 144 validated cases in test/dev splits, manifests, `test.sha256`, peer-checked labels | `faultgen/`, 4 dev cases, validator (3 runs, ~3 min/case) | about 140 more cases, true distances, freeze hash; I check 10 random labels | P1-S07, P3-S04, P4-S01, P5-S03, P5-S04 | **critical path, blocks** |
| 3 | P1-S01 / P1-S02 hardening | lab realism fix, worker tests, sandbox on his machine | `lab/`, `sandbox/` | re-run on his laptop, fix flaky points | P2-S04 (real runner), P1-S07 | blocks real-sandbox evidence |
| 4 | P2-S01/S02/S03 finishing | collector CLI, 004 hint, graph precision, E1 on a real dataset | existing modules, retrieval spike | E1 needs traces and a larger case set | P2-S07, P3-S04 G-arm, P4-S01 | parallel with 2 |
| 5 | P3-S02 metrics on real data | metrics over real runs, edit-quality metrics | `evaluation/` | run once records exist | P3-S04 results page, P4-S01 | parallel |
| 6 | P2-S07 Sync 2 | joint session, one command running 4 cases end to end | my consumer side is wired | lead the session | P2-S07 | after 1-4 |
| 7 | P4-S02, P5-S01, P5-S02, P5-S05 (optional), P6-S01, P6-S04 | failure analysis, deeper graph, statistics, security suite, paper | none of mine overlaps | not started, deliberately untouched | P4-S03, P6-S04 support | later |
| 8 | **New, 24 Nov 2026:** Retrieval modernization study P5-S06 (benchmark + baselines), P5-S07 (embedding cache + verifier), P5-S08 (RET-E, fusion, ADR 0003), P5-S09 (optional) | offline dev-split results, new modules, ADR 0003 PROPOSED | review of section 2 code first; `retrieval/e1.py`, `evaluation/metrics/retrieval.py` | see section 6 | P5-S11 (Ruhan, conditional) | P5-S06 depends on item 1 (review) and P3-S01 (done); after items 1 to 4 as capacity allows (Q16) |
| 9 | **Proposed, 25 Nov 2026:** root-cause and impact tasks P5-S12 to P5-S16 (see section 6.1; pending owner approval Q18) | new modules, preregistered evaluation | design doc `docs/research/root-cause-impact-regression-design.md` | section 6.1 | P5-S17 (Ruhan, conditional) | after P5-S06; MVP first |

## 5. WhatsApp message
```
Hey Rafique! Quick status so we don't duplicate anything 🙏

☑ Yours and done: repo setup, backend scaffold + shared contracts (P0-S01/S02/S05), retrieval spike + limits report part A (P0-S06A)

Already in main (written by my Claude session for me, NOT reviewed by you yet, please don't rebuild, just review + extend):
☑ lab (P1-S01), sandbox (P1-S02), evidence collector (P2-S01), code graph (P2-S02), retrieval L/G (P2-S03), metrics + baseline (P3-S02). Tests pass, but I couldn't re-run the Docker ones today.
◐ seed cases (P1-S03): only 4 dev cases exist (datasets/, manifests/dev.json), faultgen is there. We need way more.

Your list, in the order I need it:
☐ 1. Review the above + my small AgentRunRecord change (optional fields replicate/temperature/seed/failure_reason, P0-S05). Details: docs/plans/RAFIQUE_HANDOFF.md
☐ 2. P1-S03 → P3-S01: grow the seed cases and freeze the dataset (hash). This is the big one, it blocks my P1-S07, P3-S04, P4-S01, P5-S03/S04. I'll peer-check 10 labels.
☐ 3. Re-run lab + sandbox on your laptop, fix flaky bits (P1-S01/S02): my P2-S04 real-runner check waits on it
☐ 4. Finish evidence/graph/retrieval gaps (P2-S01/02/03): collector CLI, case 004 hint, E1 on the bigger set. Can run parallel with 2
☐ 5. Run metrics on real runs (P3-S02): feeds my results page (P3-S04)
☐ 6. Sync 2 session with me (P2-S07)
☐ 7. Later: P4-S02, P5-S01/S02/S05(optional), P6-S01, P6-S04. I haven't touched these.

Heads up: Docker was off when I checked, so lab/sandbox live status is from my earlier run. Shout if anything looks off 👍
```

## 6. Retrieval modernization study (new, 24 Nov 2026)
Added at the project owner's instruction because retrieval, graph and metrics are your Track A. It is a **follow-up study**: it does not change or re-run the frozen experiment. Design and numbers: `docs/research/retrieval-architecture-review.md` (read sections 0, 3, 5, 7) and `docs/research/technical-findings-2026-11-24.md`. Decision D36; assumption AS11; open question Q16 (approvals, your capacity).

| Task | Effort | Depends on | Expected output | Acceptance (measurable) |
|---|---|---|---|---|
| P5-S06 Benchmark + baselines RET-L / RET-G (essential) | 1.5 d | P3-S01 (done), your review of P2-S02/S03 | harness + `results/retrieval/<run_id>/` tables on the 33 dev cases: Recall@K, Precision@K, MRR, nDCG, source-localization, evidence coverage, context tokens, latency, paired bootstrap CIs, equal-token protocol | metrics match hand-computed tests; two runs identical; fingerprint unchanged; 0 tokens |
| P5-S07 Manifest + embedding cache + verifier (essential) | 2 d | P5-S06 (data model can start in parallel) | new modules: chunk identity, manifest diff (new/modified/deleted/moved), content-addressed store, atomic `ACTIVE` pointer, resume, namespaces, verifier | six scenario tests pass with a fake embedder; crash/resume test; verifier catches tampering |
| P5-S08 RET-E + RET-LE/LG/LGE (RRF k=60) + ADR 0003 (essential, decision gate) | 2 d + model setup | P5-S06, P5-S07, model approval (Q16/AS11) | preregistration, dense/hybrid modules, results at equal budget, `docs/adrs/0003-retrieval-architecture-decision.md` (PROPOSED) | every threshold reported pass/fail with CIs; go only if H1 and H2 hold on dev |
| P5-S09 Optional reranking | 1 d | P5-S08 go | rerank arm or dropped note | gain at equal tokens with CIs, else dropped |

### 6.1 Root-cause and impact analysis tasks (PROPOSED 25 Nov 2026, NOT STARTED, pending owner approval Q18)
Design: `docs/research/root-cause-impact-regression-design.md` (sections 2 to 9). Decision D37 (proposed); assumption AS12; questions Q17, Q18. Same hard constraints as above: new modules only (e.g. `backend/traceforge/analysis/`), overlay on a graph copy, never edit `codeintel/` or RC1-fingerprinted files, 0 tokens, dev/fixture data only, no hidden tests or gold in any graph or report.

| Task | Tier | Effort (ASSUMPTION) | Depends on | Expected output |
|---|---|---|---|---|
| P5-S12 Traversal overlay + root-cause ranker | MVP | 3 d | P5-S06 | inheritance/override edges, evidence classes, budgeted bidirectional traversal, ranker with explanation paths |
| P5-S13 Config value-flow analysis | Tier 2 (after MVP gain) | 3 d | P5-S12 | value extraction (no secrets), one config chain, model-free mismatch checks |
| P5-S14 Runtime evidence fusion | Tier 2 | 1.5 d | P5-S12 | `observed` marks from frames/logs/failing test id; dev-only coverage oracle |
| P5-S15 Change-impact report + visible-test selection | MVP | 2.5 d | P5-S06 (S12 optional) | impact report, ranked visible tests, "not analysable" section, hidden-dir exclusion test |
| P5-S16 Root-cause and impact evaluation suite | MVP reduced (4 families x 3 cases, about 1.5 d); full (8 x 5, about 3 d) | 1.5 to 3 d | P5-S06; S12/S15 incrementally | fixtures, preregistered thresholds, results with CIs; Ruhan verifies labels |

P5-S17 (regression-aware repair validation) is Ruhan's, conditional, RC2 only; you support the impact/selection interface. Do not take it.

**MVP path:** P5-S06, S07, S08, S12, S15, S16-reduced. **Capacity warning:** your new work is about 6.5 d (P5-S06 to S09, earlier) plus 13 d (S12 to S16 full) = about 19.5 d full, and about 12.5 d for the MVP path. This competes with your existing Track A backlog. Capacity and timeline are an owner/Rafique decision (Q18); the tasks are NOT STARTED and proposed pending owner approval. Static analysis cannot see dynamic dispatch or reflection; nothing here claims complete root-cause or impact coverage.

Ruhan owns P5-S10 (RC2 pipeline fixes, needs owner approval) and P5-S11 (conditional end-to-end experiment; you support the retrieval wiring). Do not take those.

**How to run / where to read:** existing offline harness `task eval:retrieval SPLIT=dev` (`backend/traceforge/retrieval/e1.py`); step docs in `docs/plans/phase-5-research-completion/step-06 ... step-09`; step documents give the exact acceptance lists. Per-step commands are added to the README as each step lands.

**Constraints (hard):**
- Do not edit any of the 28 RC1-fingerprinted files (list in review section 6.1) and treat `codeintel/*` as de facto frozen; new code goes in new files not imported by frozen ones. Check `code_fingerprint()` equals `ee3d8d87...` before and after.
- Zero AxForge tokens, no network or LLM calls, no hosted embeddings; free local model only (Ollama server was not responding on 24 Nov; no torch yet; put any install and caches on D:, C: has about 3 GB free).
- Dev split only (33 cases). Never the test split (151) or the 35 analysed sites. Results only under `results/retrieval/`, never `results/final`.
- Never index hidden tests, `mutation.patch`, gold manifests or fault-generator artifacts.
- Gold labels are used by the scorer only. Preregister hypotheses before running.
- Files <= ~300 lines, feature folders, one runnable check per non-trivial piece (`docs/invariants/core.md`); commit on `main`, update TWD section 0 in the same commit.

**Known inconsistencies (not fixed here, do not rely on the stale side):** (1) step docs and phase READMEs say NOT STARTED where TWD/this file say IMPLEMENTED; (2) TWD section 3 ticks few items vs section 0; (3) P2-S02/P2-S03 owned by you but authored by Ruhan's session and unreviewed; (4) P3-S04/P4-S01/P2-S05/P2-S06 status differs between TWD and the Ruhan tracker; (5) TWD step counts (19/20) do not equal the primary-step lists; (6) P0-S06 Part A status differs and `spikes/retrieval` is not listed in main's tree; (7) the "graph decision ADR" required by P5-S01/P5-S03 does not exist (ADR 0003 is proposed to cover it, owner approval pending); (8) P2-S03's embeddings checklist item is still open; (9) TWD section 6 ownership-consistency claim; (10) Taha still named in `docs/demo/a3-demo.md`; (11) context-budget figures disagree (D20 ~4,000 vs code 3,000 tokens); (12) step docs name branches though D33 says none.

## 7. Status sync 2026-11-25: Ruhan-side duties and the 12 inconsistencies
**Ruhan-side review duties (outstanding, not done):** Rafique has not reviewed any Ruhan task; Ruhan has not approved the Track A code authored by his Claude-assisted session (P1-S01, P1-S02, P2-S01..S03, P3-S02). Rafique's review list for Ruhan's code: P0-S03, P1-S04..S07, P2-S04..S06, P3-S03, P3-S04, P5-S10 (RC2 opt-in files `agent/rc2/*`, `tests/agent/test_rc2.py`, `results/rc2/rc2-fingerprint.txt`), P6-S02 (CI is Rafique-owned for branch protection), P6-S03, plus the additive `AgentRunRecord` change. Evidence per task: `RUHAN_TASK_TRACKER.md`. Rafique should run `tests/integration` and the compose stack on his own machine.

Status of the 12 inconsistencies listed in section 6:
1. Step docs say NOT STARTED: FIXED for Ruhan's 20 steps and the phase README rows (labels plus evidence line). Rafique's step docs are unchanged (his to update).
2. TWD section 3 ticks vs section 0: unchanged by design; a tick means approved, and nothing of Ruhan's is approved.
3. P2-S02/S03 owned by Rafique, authored by Ruhan's session, unreviewed: NOT RESOLVABLE here (needs the review).
4. P3-S04/P4-S01/P2-S05/P2-S06 status differences: FIXED (tracker authoritative; TWD and roadmap synced).
5. Step counts: FIXED. Ruhan 20 primary; Rafique 28 (the 27 in the TWD 2.1 list plus P0-S06 Part A, now added to that list). Earlier 22/23 for Ruhan were wrong.
6. P0-S06 Part A status: roadmap now says "A DONE; B ... IMPLEMENTED, PARTLY RUN". `spikes/retrieval` exists on disk (verified 25 Nov by directory listing); whether it is tracked on `main` was not checked.
7. Graph decision ADR missing: UNRESOLVED. ADR 0003 stays PROPOSED with its decision blank (owner).
8. P2-S03 embeddings checklist item: UNRESOLVED (Rafique's P5-S08 gate).
9. TWD section 6 consistency claim: FIXED (Synverk is not used; see plans README).
10. Taha in `docs/demo/a3-demo.md`: FIXED.
11. Context-budget figures (D20 ~4,000 vs code): UNRESOLVED, not re-measured today; D20 stays provisional.
12. Step docs name branches though D33 says none: unchanged; `plans/README.md` already says the Branch field is ignored.


## 8. Interim checkpoint handoff (2026-11-25, `origin/main` @ `4e1af6d`)

Pushed so you can work independently while Ruhan finishes his remaining tasks. This is an **interim** checkpoint, not the final merge. `git pull --ff-only` first; nothing of yours was overwritten (the only commits on top of `17ef0f4` are the six listed below).

**What is on `main` now (six commits):** RC2 opt-in fixes (`agent/rc2/`, separate fingerprint); regression/impact layer (`regression/`); frontend Investigate flow and review a11y; CI changes plus eval scripts; backend (investigate route, pipeline v5, evaluation, retrieval, repair, evidence); docs sync (plans, trackers, ADRs, research, demo).

**Your tasks are untouched and NOT STARTED:** P5-S06 to S09, P5-S12 to S16 (owners unchanged). Start with P5-S06 and P5-S07 (parallel, zero tokens), then S08; S12 and S15 can start after S06. Design: `docs/research/retrieval-architecture-review.md`, `docs/research/root-cause-impact-regression-design.md`, ADR 0003 (PROPOSED, decision blank).

**Frozen, do not edit:** the 28 RC1 behaviour files listed in `backend/traceforge/evaluation/fingerprint.py` (`FILES`). RC1 fingerprint must stay `ee3d8d873a6e939451650d031a919799138e621859f79bdd91994af3f6456b51` (verified from a clean export of this commit). Build new code in new modules (for example `traceforge/analysis/`, new retrieval modules) and graph overlays on a copy; do not modify `codeintel/` behaviour in place. Check: `cd backend && .venv/Scripts/python.exe -c "from traceforge.evaluation.fingerprint import code_fingerprint as f; print(f()['sha256'])"`.

**Interfaces to build against**
- Impact: `traceforge/regression/impact.py` defines `ImpactProvider` (`analyse(base_root, patched_root, *, visible_tests, hidden_paths, seeds)`), the sealed `ImpactReport` (with `impact_sha256`) and a default `GraphImpactProvider` over existing `codeintel` (`impact_set`). Register your P5-S15 provider with `register_impact_provider`; it is loaded lazily from `traceforge.analysis.impact_report.make_provider`. Spec: `docs/research/regression-validation-contract.md`.
- Retrieval: `regression/retrieval_adapters.py` has a `RetrievalAdapter` registry (RET-L, RET-G registered; register RET-E / RET-LE / RET-LG / RET-LGE from your modules). The downstream experiment check refuses to start unless ADR 0003 says `go` and a token budget is recorded.
- Test selection and patch history: `regression/selection.py`, `history.py`, `runner.py` (wraps the existing repair runner without editing `repair/loop.py`).
- Evidence classes `static | observed | inferred | unknown`: the default provider emits static, inferred, unknown; `observed` and the overlay (inheritance, value flow) are yours (P5-S12, S13, S14).

**Local environment notes**
- Ollama (0.40.17) did not respond until `ollama serve` was started manually. Models present: `qwen3.5:4b-q4_K_M`, `medgemma:4b`, `all-minilm:22m` (384-dim embeddings work, first call ~23 s with model load). No code-specific embedding model is downloaded; picking one is your P5-S08 call. The earlier HTTP 400 was Ollama's default 4096-token context; a variant with `num_ctx 12288` (`qwen3.5-4b-ctx12k`, made with `ollama create`) fixes it.
- `results/` and `runs/` are git-ignored. The frozen RC1 results, evidence bundles and ledgers exist only on Ruhan's machine. You do not need them for retrieval work: regenerate evidence bundles locally (zero tokens) with `python -m traceforge.agent.lab_collect --manifest datasets/manifests/dev.json --case <id>`; use the dev split only (gold for scoring only, never as input).
- Run pytest from one test directory per call (the `conftest.py` files collide). Frontend: node and npm only (no pnpm locally).

**Incomplete on Ruhan's side (still in progress after this push):** real end-to-end investigate run with a patch (BeatAPI returned 503s; re-run with local Ollama pending), RC2 dev validation (pending), P5-S04 local-model comparison (pending), research statistics for P4-S01 / P5-S03, final docs sync. Any of these may land as later commits; pull before you push.

**Rules that still apply to everything you add:** no secrets or keys in code or logs (keys come from env or settings only); no hidden-test content in prompts, retrieval inputs or feedback; no AxForge spend without owner approval (retrieval work needs none); normal pushes only, no force-push or history rewrites.

## 9. Final sync (2026-11-25, `origin/main` up to `64073ca`)
The interim checkpoint in section 8 is superseded by later pushes; CI on `64073ca` is green on all four jobs (backend ruff+pytest, contracts, frontend, docker). `git pull --ff-only` before you push.
- **Contract schema JSON changed additively:** `agent_run_record` and `evidence_bundle` schemas gained optional fields. They were regenerated and pushed (the CI drift check failed on the stale files before). Please review as the shared-contract owner (P0-S05).
- **Small result summaries are now tracked:** `results/rc2`, `results/p5s04`, `results/analysis` summaries (`.gitignore` updated). Raw analysis outputs stay local and untracked.
- **CI fixes** in `.github/workflows/ci.yml` (pnpm, drift check); ruff E501/I001 fixed; a test that depended on a missing DB password env var is now hermetic.
- **Q19 is DECIDED:** the reduced RC1 evaluation is the A3 final evaluation for diagnosis/repair, shortfall disclosed; retrieval E1 was run offline on all 151 frozen test cases (`docs/research/a3-evidence-and-statistics.md`). No graph-superiority and no feedback-effect claim.
- **Ruhan-side `regression/` layer** (26 tests) exposes the `ImpactProvider` and `RetrievalAdapter` hooks from section 8; it is not integrated yet (needs your P5-S15 provider and a sandbox `run_selected` adapter).
- Your tasks (P5-S06 to S09, P5-S12 to S16) remain NOT STARTED. Rafique review of Ruhan's tasks is still outstanding.

## 10. Retrieval and analysis work implemented at the owner's direction (2026-11-25, checkpoint 2)

On 25 Nov the owner told Ruhan's session to build the retrieval-architecture tasks rather than wait. **Ownership in the plans is unchanged (Rafique owns P5-S06 to S09 and S12 to S16); the code below was written by Ruhan's Claude-assisted session and needs Rafique's review.** Nothing here touches the 28 frozen RC1 files, `codeintel/`, `results/final` or `datasets/`; all of it is new packages. Zero provider tokens were spent; embeddings use local Ollama only.

| Task | State | Where | Evidence |
|---|---|---|---|
| P5-S06 benchmark and baselines | IMPLEMENTED, TESTED (25 tests) | `traceforge/retrieval_bench/`, `benchmarks/retrieval/` (3 pinned repos: itsdangerous 2.2.0, requests v2.32.3, this repo's `lab/`; 45 queries, 98 gold units), `docs/research/retrieval-benchmark-baselines.md` | Labels were authored by Claude and need an independent second check (`benchmarks/retrieval/second_review.csv`). On the 45 repo queries RET-G equals RET-L (no anchors in free text); on the dev split G beats L at recall@5 (sign test p=0.031, n=12 scored dev cases). |
| P5-S07 incremental index and embedding cache | IMPLEMENTED, TESTED (17 tests, all six scenarios, crash safety, dims refusal) | `traceforge/index/`, `docs/research/incremental-index-measurements.md` | `lab/` 280 chunks: cold sync 34.3 s (276 texts embedded), warm resync 0.033 s with 0 embeds, 635 KB. Peak RSS not measured. |
| P5-S08 dense retrieval, fusion, ADR 0003 | PARTIAL: code and preregistration written, 10 tests pass, evaluation runs started (`results/retrieval/p5s08-*`, local only); the written evaluation and ADR 0003 outcome were NOT finished (the session hit its usage limit) | `traceforge/retrieval_next/`, `docs/research/embedding-hybrid-preregistration.md` | Finish: run the preregistered arms on all repairable dev cases, write `docs/research/embedding-hybrid-evaluation.md` and the ADR 0003 recommendation. ADR 0003 stays PROPOSED with the decision blank. |
| P5-S12 traversal overlay and ranker | IMPLEMENTED, TESTED; preregistered rule says NO-GO (equals graph distance on call chains; helps on configuration and hub cases) | `traceforge/analysis/` | 41 tests in `tests/analysis`. |
| P5-S15 impact report and test selection | IMPLEMENTED, TESTED; GO on the reduced fixtures (selection recall 1.0, 0.575 of suite selected, 0 hidden leaks) | `traceforge/analysis/impact_report.py`, provider `s15` (registered lazily by `traceforge/regression/`) | Fixtures are small. |
| P5-S16 reduced evaluation | IMPLEMENTED (23 fixtures, hand-labelled, thresholds preregistered first) | `benchmarks/rootcause/`, `docs/research/rootcause-impact-evaluation.md` | Thresholds R1, R2, R5 failed (reported as such). `benchmarks/rootcause/expected_relationships.csv` needs a second reviewer. |
| P5-S09, S13, S14 | NOT STARTED | n/a | Gated on S08 and the MVP result (S09), Tier 2 (S13, S14). |

Known open points for your review: second-reviewer label checks for both benchmarks; S08 completion; a peak-memory measurement for the index; the regression tests now expect provider `s15` to exist. Local environment notes in section 8 still apply (Ollama models: `all-minilm:22m` plus whichever small embedding models S08 pulled, recorded in its prereg and results; C: has only about 1.9 GB free).
