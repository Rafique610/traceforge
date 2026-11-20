# P2-S04 — Repair loop and independent verification

## A. Task identification
| Field | Value |
|---|---|
| Phase | 2 Evidence-to-repair |
| Step | 4 |
| Task ID | P2-S04 |
| Synverk card | TRAC-15 |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | Muhammad Rafique (sandbox questions) |
| Reviewer | Muhammad Rafique |
| Priority | Normal |
| Effort | 3.5 days |
| Status | NOT STARTED |
| Branch | `ruhan/P2-S04-repair-loop` |

## B. Objective
Turn a proposed diff into a verified, rejected or unverified result, with the two feedback conditions differing **only** in whether the model sees visible-test output. This is the second independent variable of the research question and the main safety mechanism: a patch is only "verified" if pre-written hidden tests, which the model never sees, pass.

## C. Prerequisites
- P1-S06 (patch stage), P1-S02 (`run_tests`; use a fake runner returning sample `TestRunResult`s until it merges), P1-S03 (real seed cases).
- Read `docs/invariants/security.md` ("Hidden acceptance tests never enter the model's context").

## D. Technical background
- **Attempts:** both F0 and F1 get up to 3 attempts (design fix D10). F0: each attempt is a fresh patch request with the same diagnosis and context. F1: attempts 2–3 include the **visible** reproducer/test output from the previous attempt (capped). Stop early when visible tests pass.
- **Hidden gate:** after the loop, run the hidden suite once on the final patch. Its result goes into the `AgentRunRecord` and the DB, never into a prompt.
- **Outcomes:** `TEST_VERIFIED_IN_LAB` (reproducer failed on base and passes on patch, hidden passes, existing visible suite passes), `REJECTED` (any of those fail, or policy blocks), `UNVERIFIED` (runner couldn't execute), `NO_PATCH` (non-repairable diagnosis).
- **Diff policy:** parse with a strict unified-diff parser (stdlib `difflib` can't parse; write a small parser or use `unidiff` — decide in the PR, prefer the smaller dependency); reject paths outside the service directory, any `tests/` path, binary/symlink changes, renames, and diffs over 60 changed lines.
- **Worktrees:** `git worktree add <tmp> <base_sha>` per attempt, apply the patch with `git apply --check` then `git apply`, remove after.

## E. Implementation instructions
1. **`repair/patch_policy.py`:** `check(diff_text, service) -> PolicyResult(ok, reasons, changed_paths, changed_lines)`.
2. **`repair/worktree.py`:** context manager creating/removing a worktree at `base_sha`; applies a diff; returns the path.
3. **`repair/loop.py`:** `repair(case, diagnosis, context, condition) -> RepairResult`:
   - baseline: run `reproducer` on base (must fail; if it passes, record `UNVERIFIED` with reason `fault_not_reproduced`);
   - for attempt in 1..3: request patch (F1 adds previous visible output), policy check, apply, run `reproducer` + `visible`; break on pass;
   - hidden: run `hidden` once on the final applied patch;
   - freeze: store diff text and `patch_sha256`.
4. **Persistence** (Ruhan's DB lane): `patches` (id, incident_id, diff, sha256, attempt, policy_ok), `validation_runs` (patch_id, suite, passed, failed, timed_out, duration_ms); Alembic migration.
5. **State transitions:** `PATCH_PROPOSED → VALIDATING → VERIFIED|UNVERIFIED` with the red/green payload the P1-S04 guard requires.
6. **No-leak test** `tests/integration/test_no_hidden_leak.py`: run an F1 case from cache with a recording gateway; assert no prompt contains any hidden test ID, hidden file name, or hidden output line.
7. **Policy tests:** path escape (`../`), test file, binary, oversize, rename.
8. **Equal-attempts test:** F0 and F1 both call the patch stage up to 3 times when visible tests keep failing.
9. CLI `task repair:run CASE=<id> CONDITION=G1`.

Edge cases: patch applies but breaks import → visible fails → next attempt; runner timeout → `UNVERIFIED` (never success); model returns identical diff each attempt in F0 → allowed (temperature 0), recorded.

**Additions from the feasibility review (21 Nov 2026; see D18–D24)**
- Edit format: **search/replace blocks** (D19, confirmed by P0-S06). The applier converts accepted edits to a unified diff for storage and hashing. An edit whose old lines don't match exactly is invalid and uses up the attempt.
- Size cap: ≤60 changed lines and ≤2 files per patch; edits to test files are rejected.
- Each attempt runs the **whole** visible suite, not only the failing test, so a fix in file A that breaks file B is caught.
- Flag any change to a function's parameters (AST compare) in the patch record.

**Gap fixes (21 Nov 2026; see D26–D31)**
- Reject a patch that adds a literal value copied from a visible test (string or number from the test's inputs/asserts, excluding 0, 1, '' and None) and record it as `REJECTED` with reason `test_literal` (D31).

## F. Checklist
- [ ] Diff parser + policy with reasons
- [ ] Worktree manager (create, apply, cleanup)
- [ ] Baseline reproduction check
- [ ] Attempt loop with F0/F1 behaviour and early stop
- [ ] Hidden suite once, result never in prompts
- [ ] Patch freeze + SHA-256
- [ ] `patches` and `validation_runs` tables + migration
- [ ] State transitions with red/green payload
- [ ] No-leak integration test
- [ ] Policy tests; equal-attempts test
- [ ] CLI task
- [ ] Seed config + code results pasted on TRAC-15
- [ ] Search/replace applier + diff conversion
- [ ] Size cap and test-file block
- [ ] Whole visible suite per attempt
- [ ] Signature-change flag
- [ ] Test-literal check with a unit test that catches a special-cased input

## G. Expected deliverables
New: `backend/traceforge/repair/{patch_policy,worktree,loop}.py`, models/migration, tests. Modified: `agent/pipeline.py` (calls repair), `Taskfile.yml`, `README.md`. Interface: `repair(...) -> RepairResult`.

## H. Testing and validation
- No-leak and equal-attempts tests pass.
- Seed config and code cases reach `TEST_VERIFIED_IN_LAB`, or the failure is explained on the card (e.g. model wrong) — the machinery must be correct either way.
- Acceptance: a hand-written correct patch for the code seed case is verified; a hand-written wrong one is rejected by the hidden suite.

## I. Dependencies and integration
- **Informed by:** P0-S06 limits report.
- **Depends on:** P1-S06, P1-S02, P1-S03.
- **Unblocks:** P2-S05, P2-S07, P3-S04.
- **Integration:** consumes Rafique's `run_tests`; produces `outcome`/`patch_sha256` in `AgentRunRecord` for P3-S02.

## J. Definition of done
Merged after Rafique's review; all listed tests pass; correct/incorrect hand patches behave as expected; TRAC-15 approved.
