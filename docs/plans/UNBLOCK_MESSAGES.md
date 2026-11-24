# Who must act, and ready-to-send messages (drafted 2026-11-21; nothing has been sent)

## 1. What only Ruhan can do
| # | Action | Unblocks |
|---|---|---|
| R1 | Check whether Mistral's free Experiment plan serves `devstral-small-latest` (console.mistral.ai → API keys / models). If yes, create a key and add it to `.env` with the PowerShell prompt (never in chat) as `TRACEFORGE_MISTRAL_API_KEY`; then tell Claude so the free allowlist can include `mistral` and the Devstral vs Qwen probe can run. If no, decide how to proceed (Devstral stays the intended model; nothing is substituted automatically). | D21, ADR 0001, all model comparison |
| R2 | Provide the proposal PDF (kept outside the repo; a revised one dated 23 Nov now exists) and, if wanted, ask the supervisor to confirm the revised version in writing (the 18 Nov email already gives conditional permission to proceed). | P0-S04, P4-S03 |
| R3 | Approve (or send back) the steps now in NEEDS REVIEW: P0-S03, P1-S04, P3-S03 (and the others once evidence is accepted). AGENTS.md: only Ruhan approves. | checklist closure |
| R4 | Decide commit strategy when ready (nothing is committed). | delivery |
| R5 | Rotate the OpenRouter key if the earlier one was not deleted (it appeared in chat). | hygiene |

## 2. What only Rafique can do (Track A — message to send)
> Hi Rafique — Ruhan's Track B pieces are implemented locally on branch `ruhan/stage-b-work` (not pushed). To integrate for real I need these from you, in this order:
> 1. **Contract heads-up (B9):** I made an additive change to `AgentRunRecord`: `provider` is now a free-form slug (was mistral/ollama/groq) and there are new optional fields `replicate`, `temperature`, `seed`, `failure_reason`. Schemas regenerated. Please review `backend/traceforge/contracts/agent_run.py`; I did not change any other contract.
> 2. **Your spike branch** `rafique/P0-S06-retrieval-spike` is unmerged on `main`; I copied your Part A files into my tree untracked, unchanged. Part B (model probe) is filled in `docs/research/limits-report.md`.
> 3. **P1-S02 sandbox:** I call `run_tests(TestRunRequest) -> TestRunResult` with `worktree_path` repo-relative; my repair loop currently uses a stand-in runner (real pytest in a temp git repo), which is NOT your sandbox. Tell me the final import path and whether the worktree is host-mounted or copied.
> 4. **P1-S03 seed cases:** manifest file format (JSON list of `CaseManifest`? one file per case?) and where `visible`/`hidden` tests live. My runner's `load_manifest` is a single swap point. For P1-S07 I need the 4 seed cases.
> 5. **P3-S01 freeze:** my runner refuses `split=test` unless `test.sha256` sits beside the manifest and equals its SHA-256 — confirm that matches your freeze record.
> 6. **P2-S01/S03 real evidence/context:** my agent consumes `EvidenceSource.collect(...)` and `ContextSource.retrieve/read_symbol/neighbors(...)`; please implement those protocols (see `backend/traceforge/agent/sources.py`) or tell me what to change.
> 7. **P3-S02 metrics:** my results page shows raw counts only; it will show your computed metrics when the report JSON format exists.
> 8. **AS9:** where should GitHub intake issues live (a `traceforge-lab-issues` repo or labelled issues here)? Intake works on any allowlisted public issue (tested live on pallets/flask).
> 9. Model: the primary is still Devstral (`devstral-small-latest`); free access is unconfirmed (see `docs/orchestration/DECISIONS.md` B7/B11).

## 3. What only the supervisor can do
Q3 is ANSWERED-CONDITIONAL: the 18 Nov 2026 email gives conditional written permission to proceed (evidence in `D:\TraceForge\Assignment_3_TraceForge\Evidence\`). Still open: written confirmation of the revised proposal and R&D Product track. Optional draft email: `docs/plans/phase-0-foundation/step-04-proposal-update-draft.md` (written before the email arrived, 21 Nov). Keeps P0-S04 PARTIALLY COMPLETE.
