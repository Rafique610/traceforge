# P6-S01 — Security hardening

## A. Task identification
| Field | Value |
|---|---|
| Phase | 6 Productization and paper |
| Step | 1 |
| Task ID | P6-S01 |
| Synverk card | TRAC-26 |
| Primary owner | Muhammad Rafique |
| Supporting | Muhammad Ruhan Kamran (agent-side fixtures) |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Low (A4) |
| Effort | 2.5 days |
| Status | NOT STARTED |
| Branch | `rafique/P6-S01-security-suite` |

## B. Objective
One security suite that proves every safety claim in the proposal and fails loudly if any guard is removed: prompt injection, sandbox isolation, path policy, secret handling, hidden-test isolation, review binding. Use the **backend-security-coder** skill.

## C. Prerequisites
- A3 delivered; guards already exist in P1-S02, P1-S06, P2-S01, P2-S04, P2-S05, P2-S06.
- A3 failure analysis entries tagged `MISLEADING_LOG_INJECTION` (if any).

## D. Technical background
- **Mutation-style check:** for each guard, a test asserts the protective behaviour; a companion script temporarily disables the guard (monkeypatch) and confirms the test fails. This proves the test actually covers the guard.
- Injection fixtures go in logs, code comments, Compose labels and GitHub issue bodies, with payloads like "ignore previous instructions", fake tool names, fake "SYSTEM:" headers, and instructions to print env vars.

## E. Implementation instructions
1. `tests/security/test_prompt_injection.py`: run the pipeline from cache/fake gateway on cases with injected text; assert the tool set is unchanged, outcome class unchanged, no new tool names accepted.
2. `tests/security/test_sandbox.py`: no network, memory cap (allocate beyond limit → killed), pids cap (fork bomb → contained), timeout, read-only root, no `/var/run/docker.sock`, non-root UID.
3. `tests/security/test_patch_policy.py`: path traversal, absolute paths, test-file edits, binary, symlink, oversize.
4. `tests/security/test_secrets.py`: secrets from a test `.env` never appear in evidence, prompts (recording gateway), retrieval index, reports or logs.
5. `tests/security/test_hidden_isolation.py`: hidden tests not visible in the worktree; never in prompts (extends P2-S04's test to all conditions).
6. `tests/security/test_review_binding.py`: tampered hash, wrong state, replay of an old review.
7. `scripts/guard_mutation.py`: disables each guard in turn and confirms its test fails; output pasted on TRAC-26.
8. Threat model summary in `docs/security/threat-model.md` (assets, entry points, mitigations, residual risks such as Docker not being a hard boundary).

## F. Checklist
- [ ] Injection fixtures across 4 channels
- [ ] Prompt-injection tests
- [ ] Sandbox isolation tests
- [ ] Patch-policy tests
- [ ] Secret-handling tests
- [ ] Hidden-test isolation tests
- [ ] Review-binding tests
- [ ] Guard-mutation script and results
- [ ] Threat model doc
- [ ] Suite included in `task test` and CI

## G. Expected deliverables
New: `tests/security/*`, `scripts/guard_mutation.py`, `docs/security/threat-model.md`, injection fixtures.

## H. Testing and validation
- Suite green; guard-mutation script shows every guarded test failing when its guard is off.
- Acceptance: no secret value found by a grep over all run artifacts.

## I. Dependencies and integration
- **Depends on:** P4-S03.
- **Feeds:** P6-S02 (CI), P6-S04 (paper's safety section).

## J. Definition of done
Merged after Ruhan's review; suite in CI; mutation results posted; TRAC-26 approved.
