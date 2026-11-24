# Assignment 3 demo script (about 8 minutes)

**Status 2026-11-25: script rewritten to match the real UI; a dry run has NOT been done.** Presenters are the two team members, Rafique and Ruhan (the team is two people). Cases refer to the dev split.

## Before starting
1. `task lab:up`, `task db:up`, `task db:migrate`, `task dev` (API), `task web` (UI at http://localhost:5173). Check the header badge says "API ok" (`GET /health`).
2. The **Investigate** button starts a real investigation. It needs the backend started with `TRACEFORGE_MANIFEST` set to the case manifest and a model provider key in `.env` (never shown on screen). Without a provider the API answers 503 and the UI shows: "No model provider is configured, so the investigation could not start." plus the server detail. That message is the honest fallback; do not present a stored run as a live one.
3. The Investigate path was verified only with a fake gateway (`tests/integration`, 7 tests) and component tests; it has NOT been run live against a real provider with the real sandbox. If it is not rehearsed, use the saved-run fallback below.

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
| 9 | Results and honesty | Rafique / Ruhan | Results page and the `results/final` report (RC1): 35 sites at replicate 0, 12 at replicate 1, 8 at replicate 2 (23 sites have one replicate); L1 and G1 reuse the L0/G0 diagnosis, so they differ only in feedback; feedback was exercised in 1 case. Show the honest empty state in the factorial view where data is missing | A **reduced** evaluation, not the full protocol and not L0 vs G0 on at least 50 cases. No claim that the graph arm or feedback is better; the differences are inside replicate noise. |
| 10 | Close | Ruhan | Limitations (below), open decisions, Assignment 4 plan | Next: harder and larger cases, the owner's decision on the A3 protocol, optional RC2 validation. |

## Limits to state out loud
- Reduced evaluation only (`docs/research/final-evaluation-report.md`, `final-evaluation-stage2.md`); the benchmark is nearly saturated and cannot separate the arms.
- Investigate has not been verified live with a real provider; the default sandbox factory is untested live.
- Supervisor evidence: the 18 Nov 2026 email (Akhtar Jamil to Ruhan, 10:41 AM) says "You may proceed with the project after incorporating the recommended changes" (conditional written permission to proceed; evidence in `D:\TraceForge\Assignment_3_TraceForge\Evidence\`). It is not written approval or sign-off of the revised proposal, and the supervisor's verbal approval of the revised version is not a written document.
- No public deployment, no GitHub Actions run so far.

Fallbacks: if the live model is slow (a case can take 2-9 minutes at high reasoning effort), open a saved run from `runs/e2e/` and say so; if Docker is down, show screenshots from `docs/screenshots/`.
Do not show: `.env`, API keys, the token ledger values as proof of billing status.
