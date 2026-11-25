# Decisions and open questions

Three kinds of entries, never mixed:
- **Confirmed:** decided by the team in conversation, written in repo docs, or set on the board.
- **Assumption:** reasonable default used for planning; must be confirmed or changed.
- **Open:** not decided; blocks or affects a step.

## Confirmed decisions
| # | Decision | Source |
|---|---|---|
| D1 | Scope: configuration and Python code faults only; infrastructure is read-only evidence; no production deployment; no MoE; no multi-agent; no fine-tuning | Supervisor review; `docs/domain/traceforge/index.md` |
| D2 | Track: R&D Product | Proposal; domain doc |
| D3 | Team: Muhammad Rafique and Muhammad Ruhan Kamran (Taha Ahmed no longer on team) | User, 19 Nov 2026 |
| D4 | Work split: Track A Rafique (evidence side), Track B Ruhan (agent side); separate folders; contracts shared | User approved; `end-to-end.md`; card titles |
| D5 | Budget USD 0: primary LLM Mistral free tier (pinned Devstral), comparator Qwen2.5-Coder-7B via Ollama, spare Groq | User choice |
| D6 | Repo public at `Rafique610/traceforge`; `main` blocks force push and deletion; **no approving review required**, either member may merge their own work (required review removed 19 Nov 2026) | User, 19 Nov 2026; verified via GitHub API |
| D7 | Frontend: Vite + React + TypeScript | User choice |
| D8 | Course PDFs and `INSTRUCTIONS.md` are git-ignored | `.gitignore` |
| D9 | Outcome classes: configuration, application_code, runtime_dependency (no patch), insufficient_evidence (abstain) | Domain doc; review fix |
| D10 | Fair design: trace anchoring in both retrieval arms; both feedback arms get 3 attempts; hidden tests run once and never feed back | Domain doc; review fixes |
| D11 | Five safeguards: distance labels, pipeline-first agent, rule baseline, LLM response cache, freeze before tuning | User approved; PR #1 |
| D12 | AI components evaluated: retrieval, diagnosis, repair; report is a deterministic template | Domain doc |
| D13 | Tooling: Python 3.12 + uv, pnpm, pytest/Vitest, ruff, Taskfile, Docker Compose | `docs/invariants/tooling.md` |
| D14 | DB access via SQLAlchemy 2 + Alembic (agent chose; user had no preference) | `docs/invariants/backend.md` |
| D15 | Dataset targets: ≥60 config, ≥60 code, ≥12 runtime_dependency, ≥12 insufficient_evidence held-out; ≥30 dev | Domain doc; TRAC-19 |
| D16 | The docs in `docs/plans/` are the plan; Synverk is not used for this project (TRAC-n kept as references) | User, 19 Nov 2026 |
| D17 | Before any work, fetch and pull `main`/the current branch if it is behind `origin` | User, 19 Nov 2026; `docs/invariants/processes.md` |
| D18 | Retrieval benchmark E1 adds R0 ripgrep and a trace-only reference to L and G; embeddings optional. **Confirmed** by P0-S06 Part A | User, 21 Nov 2026; P2-S03; limits report |
| D19 | Edit format: search/replace blocks, ≤60 changed lines, ≤2 files, no test files; stored as unified diff. **Provisional** until P0-S06 | User, 21 Nov 2026; P2-S04 |
| D20 | Per-prompt context budget = measured usable size from P0-S06, not the advertised window. **Provisional** | User, 21 Nov 2026; P1-S06 |
| D21 | Primary model stays Devstral (Mistral free tier) unless P0-S06 numbers say otherwise. **Provisional** | User, 21 Nov 2026; P1-S05 |
| D22 | Code map available identically in both retrieval arms (context or diagnose tool). **Confirmed**: ~173 tokens for 22 functions in P0-S06 | User, 21 Nov 2026; P2-S02, P2-S03, P1-S06; limits report |
| D23 | Graph keeps reverse edges; report lists the impact set of changed symbols; signature changes are flagged | User, 21 Nov 2026; P2-S02, P2-S04, P2-S05 |
| D24 | `log_format` varies across cases (plain/json/uvicorn_access/none); metrics broken down by it | User, 21 Nov 2026; P1-S03, P3-S01, P3-S02 |
| D25 | Feasibility prototype P0-S06 runs before Phase 1 feature work that depends on model or retrieval limits | User, 21 Nov 2026 |
| D26 | Cache key = prompt hash + model ID + replicate index; replicates are real reruns; if the provider proves deterministic, say so and treat replicates as one | Gap Q10; P1-S05, P5-S03 |
| D27 | Dataset validator runs broken and original 3× each and rejects flaky cases; freeze record counts rejections | Gap Q11; P1-S03, P3-S01 |
| D28 | Ruhan writes or blind-reviews ≥25% of fault templates before any graph tuning; noted as a threat to validity | Gap Q12; P3-S01, P6-S04 |
| D29 | Small informal usefulness study in A4: 3–5 classmates rate 6 reports each on a 4-question rubric | Gap Q13; P6-S03, P6-S04 |
| D30 | Sandbox reuses a warm image per `base_sha`; container start and test time measured; P5-S03 time budget comes from those medians | Gap Q14; P1-S02, P5-S03 |
| D31 | Anti-overfitting: hidden tests use different inputs; patches adding visible-test literals are rejected (`test_literal`); rejections reported by reason | Gap Q15; P2-S04, P3-S01, P3-S02 |
| D32 | Anchor only the innermost 2 project trace frames; other frames are normal candidates with a bonus; E1 reports Recall@5 and @10. Graph uses edge-type weights, hub down-weighting and a returned-value edge, tuned on dev only. **Provisional** | P0-S06 Part A findings 2–4; P2-S02, P2-S03 |
| D33 | No pull requests or step branches: commit on `main`, push straight to `origin/main`; both members pull to check each other's work; never force-push | User, 21 Nov 2026; `docs/invariants/processes.md` |
| D34 | Evidence Docker proxy pinned to `tecnativa/docker-socket-proxy:v0.5.0` (was `:latest`); 66 evidence tests pass against it | Rafique review, 22 Nov 2026 |
| D35 | `AgentRunRecord` additive change approved: optional `replicate`, `temperature`, `seed`, `failure_reason`; `RULES` condition; `provider` any lowercase slug (the gateway allow-list still decides which providers may run). Closes P0-S05 | Rafique review, 22 Nov 2026 (Ruhan's B9, B13) |
| D36 | Embeddings and hybrid retrieval are a **separate follow-up study** ("Retrieval modernization", P5-S06 to P5-S11), gated by an offline dev-split benchmark with preregistered thresholds; frozen RC1 (fingerprint `ee3d8d87...`) and all its artifacts stay untouched; zero AxForge tokens for the offline stage. Tasks assigned per the owner's instruction (retrieval/graph/metrics in Rafique's Track A; RC2 and the end-to-end experiment to Ruhan). **Proposed; ADR 0003 PROPOSED, not accepted** | User, 24 Nov 2026; `docs/research/retrieval-architecture-review.md`; P5-S06..S11 **Status 2026-11-25:** P5-S06 to S08 done offline; the preregistered P5-S08 rule gave NO-GO (H1, H2, H3 FAIL, H4 PASS); recommendation: keep BM25 + graph. The decision itself is the owner's and is NOT recorded; ADR 0003 stays PROPOSED. Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; tasks stay Rafique's. |
| D37 | **PROPOSED (25 Nov 2026, pending owner approval Q18):** root-cause, dependency and change-impact capabilities are built as an **overlay in new modules** (e.g. `backend/traceforge/analysis/`) merged into a copy of the code graph; `codeintel/` and all RC1-fingerprinted files are not modified. Every edge and path carries an evidence class (`static`, `observed`, `inferred`, `unknown`). Capabilities are evaluated offline against preregistered thresholds (P5-S16) and kept only if they pass; no claim of complete root-cause or impact coverage. Changes to `repair/` (P5-S17) are RC2 only. | `docs/research/root-cause-impact-regression-design.md`; P5-S12 to P5-S17 **Status 2026-11-25:** S12 (ranker preregistered NO-GO), S15 (GO on fixtures) and S16 reduced are implemented, not approved; Q18 still open. Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; tasks stay Rafique's. |

## Assumptions (to confirm)
| # | Assumption | Used in | Confirm by |
|---|---|---|---|
| AS1 | Effort estimates in person-days are planning guesses | Roadmap, team doc | Re-estimate after Phase 1 |
| AS2 | Only Track B writes Alembic migrations; Track A returns contract objects | Integration plan | Both, at P0-S05 |
| AS3 | Run records stored as JSON files under `runs/` (git-ignored) for A3 | P3-S04 | Ruhan at P3-S04 |
| AS4 | Graph and LLM cache stored on disk keyed by SHA, not in Postgres, for A3 | Architecture | Rafique/Ruhan at P2-S02/P1-S05 |
| AS5 | Lab has its own Compose file and Postgres, separate from the app's | P1-S01 | Rafique |
| AS6 | Mistral's endpoint is OpenAI-compatible enough for the `openai` SDK | P1-S05 | Smoke test |
| AS7 | BM25 via `rank-bm25` (vs Postgres FTS) | P2-S03 | Rafique at P2-S03 |
| AS8 | Docker socket proxy image `tecnativa/docker-socket-proxy` | P2-S01 | Rafique at P2-S01 |
| AS9 | GitHub issues for intake live in a separate public repo `traceforge-lab-issues` or labelled issues on the main repo | P2-S06 | Ruhan |
| AS10 | A3 reviewer identity is a free-text name (no login) | P2-S05 | Both |
| AS11 | A free local embedding model (e.g. all-MiniLM-L6-v2, CodeRankEmbed or jina-embeddings-v2-base-code) can run on the dev machine. **Unconfirmed**: the Ollama server did not respond on 24 Nov 2026; torch and sentence-transformers are not installed; C: has about 3 GB free (use D:) | P5-S08 | Rafique at P5-S08 (before the first run) **Update 2026-11-25:** confirmed in part: local models ran via Ollama (all-minilm:22m, nomic-embed-text, jina-embeddings-v2-base-code community build); embeddings were not adopted. |
| AS12 | The config value-flow subset (values from compose and settings defaults, one config chain, one interprocedural hop, mismatch checks) can localize configuration root causes on the evaluation fixtures with stdlib `ast`. **Unmeasured**; `jedi`, `libcst`, `pycg` are TO EVALUATE. Effort figures for P5-S12 to P5-S17 are also unmeasured. | P5-S13, P5-S16 | Rafique at P5-S16 (results decide; kept only if thresholds pass) |

## Open questions
| # | Question | Affects | Owner | Blocking? |
|---|---|---|---|---|
| Q1 | Exact Devstral model ID and Mistral free-tier limits (RPS, tokens/month, data-training terms) | P1-S05, P4-S01, P5-S03 | Ruhan | Blocks experiments |
| Q2 | Official Devstral list price for the business section (only Mistral Large $0.50/$1.50 per 1M was found on the official page) | P0-S04 | Ruhan | No |
| Q3 | **ANSWERED-CONDITIONAL.** Supervisor email (Akhtar Jamil to Ruhan, Wed 18 Nov 2026, 10:41 AM), after reviewing the first proposal: TraceForge "is an interesting work", scope "a bit ambitious", core contribution to be narrowed, 13 recommended changes (see `PROJECT_REQUIREMENTS.md`). Key sentence: "You may proceed with the project after incorporating the recommended changes." This is conditional written permission to proceed. It is NOT written approval of the revised proposal, NOT a signature or sign-off, NOT a grade. The revised PDF (dated 23 Nov) incorporates the changes per the proposal's own changelog. The evidence file notes a verbal approval of the revised proposal; that is not a written document. Evidence: `D:\TraceForge\Assignment_3_TraceForge\Evidence\Supervisor_Email_Response.txt` and `Supervisor_Email_Screenshot.png`; copies in `D:\TraceForge\GCR_Upload\`. Still open: written confirmation of the revised version (P0-S04). Two tracked obligations: at least 50 labelled examples per AI component (Q19) and the isolating 2x2 comparison. | P0-S04, submission | Ruhan | No (conditional permission held) |
| Q4 | Ruhan's GitHub username, to add as collaborator | P0-S01 | Rafique | Blocks Ruhan's pushes only (merges no longer need his approval) |
| Q5 | ~~Synverk flows~~ Resolved by D16: Synverk not used | — | — | No |
| Q6 | Latency targets per case (none until measured) | NFR-03 | Both | No |
| Q7 | A4 public host (free tier) and whether login is needed | P6-S02 | Ruhan | No (A4) |
| Q8 | A4 deadline and A3 demo date: user said dates don't matter; sequencing is by dependency only | Roadmap | — | No |
| Q9 | **CLOSED for this machine (2026-11-25):** Ruhan's machine is Ryzen 5 2600, 16 GB RAM, GTX 1660 SUPER 6 GB (P5-S04 measured GPU peak 4,917 of 6,144 MiB). Rafique's laptop (reported RTX 3050 6 GB) is not recorded. | P5-S04 hardware note | Ruhan | No |
| Q10 | ~~Replicates vs cache: a cache keyed only by prompt hash makes the 3 replicates identical. Proposed: key = prompt hash + model ID + replicate index~~ Resolved by D26 | P1-S05, P5-S03 | Ruhan | No |
| Q11 | ~~Flaky tests can fake a VERIFIED. Proposed: validator runs broken and original 3× each and rejects flips~~ Resolved by D27 | P1-S03, P1-S02 | Rafique | No |
| Q12 | ~~Author bias: Rafique writes both faults and the graph. Proposed: Ruhan writes or blind-reviews ≥25% of templates before tuning~~ Resolved by D28 | P3-S01 | Both | No |
| Q13 | ~~Usefulness of the report to a human is unmeasured. Option: 3–5 classmates rate reports on a short rubric (A4)~~ Resolved by D29 | P6-S03, P6-S04 | Ruhan | No |
| Q14 | ~~Sandbox cost: container start per attempt × ~1,600 runs may dominate time. Measure in P0-S06/P1-S02; reuse warm images~~ Resolved by D30 | P1-S02, P5-S03 | Rafique | No |
| Q15 | ~~Overfitting a patch to the test (special-casing inputs). Hidden tests use different inputs; add a check that the patch doesn't contain literal test values~~ Resolved by D31 | P2-S04, P3-S01 | Both | No |
| Q16 | Approvals needed for the retrieval study: (a) which embedding model; (b) whether to change the Postgres image (not recommended; numpy flat store needs none); (c) approval to start RC2 (P5-S10); (d) AxForge spend for P5-S11 if P5-S08 says go; (e) Rafique's capacity and timeline for P5-S06 to P5-S09 (about 6.5 d) | P5-S06..S11 | Project owner (with Rafique for e) | Blocks P5-S08 (a), P5-S10 (c), P5-S11 (d) **Update 2026-11-25:** (a) models used: all-minilm:22m, nomic-embed-text, jina-embeddings-v2-base-code (primary); S08 result is no-go, so (d) AxForge spend for P5-S11 is not needed unless the owner records a 'go'; the owner decision on ADR 0003 is still open. |
| Q17 | Evaluation fixture set size for P5-S16: minimum viable 12 cases (4 families x 3) or full 40 (8 x 5). Small sets give wide CIs. Also: results directory (default `results/retrieval/<run_id>/`). | P5-S16 | Project owner, Rafique | No (MVP default 12) |
| Q18 | Approve the scope of P5-S12 to P5-S16 and the MVP (S12, S15, S16-reduced); approve or drop Tier 2 (S13, S14) and conditional P5-S17 (RC2, owner approval, token spend if any); accept Rafique's capacity impact (about 19.5 d full, about 12.5 d MVP, ASSUMPTION). | P5-S12 to P5-S17 | Project owner, Rafique | Blocks start of P5-S12 to P5-S17 |
| Q19 | **DECIDED 2026-11-25** (was OPEN, added 2026-11-25). The reduced RC1 evaluation in `results/final` (35 variant-group sites, one case per group; replicates r0=35 / r1=12 / r2=8 sites; L1/G1 patch-stage from shared diagnoses) is adopted as the Assignment-3 final evaluation for diagnosis/repair, with the shortfall against the supervisor's >=50 labelled examples per AI component disclosed. Reasoning: extending repair evaluation by 15 sites would cost about 763k tokens (mean 50.9k per site across four conditions; median 41.6k; p90 96.9k; diagnosis-only L0+G0 44.3k) against 742,728 remaining under the 4.8M ceiling, would need AxForge spend the owner has not approved, and extra cases inside existing variant groups are not independent. Retrieval meets the supervisor's >=50: E1 retrieval run offline on all 151 frozen test cases (127 with a target, 29 groups; zero tokens; evidence rebuilt as v5 symptom + visible tests, no gold), `docs/research/a3-evidence-and-statistics.md`: G minus L group-clustered 95% CI recall@5 +0.193 [+0.083,+0.321], MRR +0.048 [+0.011,+0.094], nDCG +0.044 [+0.004,+0.098], recall@10 +0.031 [-0.035,+0.122]; the configuration class (9 groups) shows no gain; recall@1 is 0 for all methods; ranking only, untuned weights, says nothing about diagnosis or repair. Rules baseline on 151: class accuracy 14/151 (9.3%), exact target 0/127. RC1 repair counts (fixed): L0 27, G0 28, L1 28, G1 29 of 35 (6 non-repairable sites, repairable denominator 29); every pairwise comparison has exactly one discordant pair, exact p=1.0; cause class L0 32 vs G0 35, 3 discordant, p=0.25. So NO graph-superiority and NO feedback-effect claim; feedback was exercised in one case (shop_api-020, two arms, not independent). Supervisor-email obligations: retrieval met; the graph-vs-feedback 2x2 done at 35 sites with CIs that do not support claims; repair component below 50 (35), disclosed. Optional: if the owner approves about 763k tokens of AxForge (not available within the ceiling), extend; otherwise disclose. P4-S01 and P5-S03 stay PARTIALLY COMPLETE (decision made; shortfall disclosed). Still open: owner approval to use RC2 (P5-S10) in any run; written confirmation of the revised scope (P0-S04; the 18 Nov email is conditional permission only, see Q3). | Owner |

## Contradictions found
| # | Where | Contradiction | Resolution |
|---|---|---|---|
| X1 | Proposal PDF vs current decisions | PDF lists 3 members, GPT-4.1-mini primary, RTX 4050 | P0-S04 updates the proposal; current decisions win |
| X2 | Audited architecture §14 vs repo rules | Layered `api/`, `db/` folders vs feature folders required by `docs/invariants/core.md` | Repo rules win; [ARCHITECTURE.md](ARCHITECTURE.md) uses feature folders |
| X3 | `main` vs PR #1 | `main` has the plan without the five safeguards; PR #1 adds them | Resolved: PR #1 and #2 merged 19 Nov 2026 |
| X4 | TRAC-10 (agent) waits on TRAC-8 (incidents API) | The agent CLI runs on samples and doesn't technically need the incidents API | Kept as on the card (card wins); this plan lists the same dependency. Can be relaxed on the board if Ruhan wants to start the agent earlier |
| X5 | TRAC-23 (A3 delivery) doesn't wait on TRAC-17 (GitHub intake) | The demo needs the real integration (rubric C4) | This plan makes P4-S03 depend on P2-S06; suggest adding TRAC-17 to TRAC-23's waits on the board (not changed here) |
| X6 | TRAC-23 is one card but covers three activities | Experiments, failure analysis, demo pack have different owners | Split into P4-S01/S02/S03 here; all map to TRAC-23 |
| X7 | AGENTS.md says `instructions.md`; the file is `INSTRUCTIONS.md` and marked superseded (history only) | Request named `instructions.md` | Read `INSTRUCTIONS.md`; its still-valid rules live in `docs/invariants/` |
| X8 | Cards name owners in titles but have no Synverk assignee | Ruhan isn't a project member | Moot (D16): owners live in the step documents |
| X9 | `INSTRUCTIONS.md` §5b says ORM only; its header says raw sqlite3 for another project | Different project | SQLAlchemy chosen (D14) |
