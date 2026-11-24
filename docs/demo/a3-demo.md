# Assignment 3 demo script (about 8 minutes)

**Status 2026-11-25 (final): script matches the real UI; a dry run has NOT been done.** Presenters are the two team members, Rafique and Ruhan (the team is two people). Cases refer to the dev split. Facts below match `docs/demo/e2e-run.md`.

## Before starting
1. `task lab:up`, `task db:up`, `task db:migrate`, `task dev` (API), `task web` (UI at http://localhost:5173). Check the header badge says "API ok" (`GET /health`).
2. The **Investigate** button starts a real investigation. It needs the backend started with `TRACEFORGE_MANIFEST` set to the case manifest and a model provider key in `.env` (never shown on screen). Without a provider the API answers 503 and the UI shows: "No model provider is configured, so the investigation could not start." plus the server detail. That message is the honest fallback; do not present a stored run as a live one.
3. The Investigate path was verified live on 25 Nov through the real HTTP path (real Postgres, real sandbox, vite proxy, local Ollama `qwen3.5-4b-ctx12k`): shop_api-001 reached DIAGNOSED correctly (configuration, `shop_api.REDIS_HOST`, SUPPORTED, 4 evidence ids), then REVIEW_PENDING, approve, CLOSED; shop_api-017 ended INCONCLUSIVE (no trace frames), reject, CLOSED. It has NOT reached PATCH_PROPOSED or VERIFIED on any real provider: the local 4B model produced `malformed_edit` and BeatAPI free returned HTTP 503 twice. A patch demo needs one owner-gated AxForge investigation (`--axforge-billing-verified`, about 30k tokens); until then show a saved run and say so.

| # | Part | Presenter | What to show | What to say (one line) |
|---|---|---|---|---|
| 1 | Problem and architecture | Rafique | Architecture slide (`docs/ARCHITECTURE.md`), healthy lab (`shop_api`, `worker`) | Failures look alike; we link runtime evidence to code and verify the fix independently. |
| 2 | Dataset | Rafique | 184 validated cases, frozen test split (151, sha recorded), dev 33 | Expected behaviour comes from running the code, not from hand-written assertions. |
| 3 | Code case, end to end | Ruhan | Create an incident for case `shop_api-002`, press Investigate (needs the provider), or open a saved run stored with `python -m traceforge.agent.e2e --case shop_api-002 --condition L0 ...`; show evidence, ranked hits and reasons, diagnosis `OrderItemIn.quantity`, diff, red then green, hidden tests pass, approve | The agent cites evidence ids; hidden tests never reach the prompt. |
| 4 | Config case with graph path | Rafique | A configuration case (for example `shop_api-001`): the hit-path view (why a file was retrieved) | G adds graph distance and config-key binding on top of the same BM25 + anchors. |
| 5 | runtime_dependency decoy | Ruhan | Case `shop_api-003`: diagnosis, no patch | A cause outside the repository is reported, not patched. |
| 6 | Abstention | Ruhan | Case `shop_api-004` | With insufficient evidence the system says so. |
| 7 | GitHub issue intake | Ruhan | Paste a public issue URL; incident with untrusted evidence; offline gives a clear error | Real integration; issue text is treated as untrusted. |
| 8 | Tampered review | Ruhan | Change the patch hash in the review request: 409 and nothing written | Approval is bound to the exact patch hash. |
| 9 | Results and honesty | Rafique / Ruhan | Results page and the `results/final` report (RC1): 35 variant-group sites at replicate 0, 12 at replicate 1, 8 at replicate 2 (23 sites have one replicate); L1 and G1 reuse the L0/G0 diagnosis, so they differ only in feedback; feedback was exercised in 1 case (shop_api-020, two arms, not independent). Fixed counts of 35 sites: L0 27, G0 28, L1 28, G1 29 (6 non-repairable); every pairwise comparison has one discordant pair, exact p=1.0. Retrieval on all 151 frozen cases: G minus L recall@5 +0.193 [+0.083,+0.321], MRR +0.048, nDCG +0.044, recall@10 not significant, configuration class no gain, recall@1 0 for all | A **reduced** evaluation adopted as the A3 final evaluation (Q19 decided 2026-11-25); the repair component has 35 sites, below the supervisor's >=50. No claim that the graph arm or feedback is better. Retrieval ranking meets >=50 but says nothing about diagnosis or repair. |
| 10 | Close | Ruhan | Limitations (below), open decisions, Assignment 4 plan | Next: harder and larger cases, the owner's decision on the A3 protocol, optional RC2 validation. |

## Limits to state out loud
- Reduced evaluation only (`docs/research/final-evaluation-report.md`, `final-evaluation-stage2.md`, `a3-evidence-and-statistics.md`); the repair component is 35 sites, below >=50 per AI component, because extending would cost about 763k tokens against 742,728 left and needs unapproved AxForge spend. The benchmark is nearly saturated and cannot separate the arms.
- Investigate was verified live only with local Ollama (diagnosis and approve/reject); no patch was produced on any real provider, so patch, impact and approve-with-patch-hash were not shown live. RC2 benefit is unproven. The local 4B comparison (12 sites) was worse than glm-5.3-flash: verified repairs 4 vs 10.
- Supervisor evidence: the 18 Nov 2026 email (Akhtar Jamil to Ruhan, 10:41 AM) says "You may proceed with the project after incorporating the recommended changes" (conditional written permission to proceed; evidence in `D:\TraceForge\Assignment_3_TraceForge\Evidence\`). It is not written approval or sign-off of the revised proposal, and the supervisor's verbal approval of the revised version is not a written document.
- No public deployment. CI is green on GitHub (run on 64073ca, four jobs), but there is no host or public URL.

Fallbacks: if the live model is slow (a case can take 2-9 minutes at high reasoning effort), open a saved run from `runs/e2e/` and say so; if Docker is down, show screenshots from `docs/screenshots/`.
Do not show: `.env`, API keys, the token ledger values as proof of billing status.
