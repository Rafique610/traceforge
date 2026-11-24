# P5-S10 — RC2 candidate: pipeline robustness fixes

Added 2026-11-24 from [technical-findings-2026-11-24.md](../../research/technical-findings-2026-11-24.md) sections 4, 5 and 7B. Independent of the retrieval study; shares only the freeze rules.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 10 |
| Task ID | P5-S10 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | — |
| Reviewer | Muhammad Rafique |
| Priority | ESSENTIAL-OPTIONAL (owner approval needed to start) |
| Effort | 2 days (planning estimate, AS1; not in the design doc) |
| Status | IMPLEMENTED (opt-in), TESTED, NOT VALIDATED, owner approval pending |
| Branch | none (commit on `main`, D33) |

**Status sync 2026-11-25.** Evidence: `pytest tests/agent/test_rc2.py` 17 passed; `results/rc2/rc2-fingerprint.txt` = fe0b6000853d7ac8b5e070b8f53bfc02216dbc77575081944f10adc5e6784e75; RC1 fingerprint ee3d8d87...56b51 unchanged. Config-value checker is standalone (wiring needs a hook in frozen patch.py/feedback.py: follow-up). Nothing calls `select_chat_fn` yet. Five-fact detail: `docs/plans/RUHAN_TASK_TRACKER.md`.

## B. Objective
Define a **separately fingerprinted release candidate RC2** = RC1 + three fixes for the only observed genuine failure modes, without altering RC1, its fingerprint (`ee3d8d87...`) or any frozen result.

## C. Prerequisites
Project-owner approval to start (Q16). RC1 artifacts archived and untouched. The analysed 35 sites motivated the changes, so they cannot confirm them.

## D. Technical background
1. Diagnosis `rationale` limit (500 characters): 8 case-runs rejected (`string_too_long`), 2 of them genuine (`shop_api-019`). Fix: tolerant handling (truncate server-side or state the limit in schema/prompt) and log the rejected text.
2. The patch loop repeats an identical wrong edit without feedback (`shop_api-020`, `"lab_redis"` three times). Fix: require a different edit or stop with a reason.
3. Config-value diagnostic: extend the unresolvable-hostname finding to propose candidate values (hostname vs compose service vs settings default).
All three edit fingerprinted files (agent diagnosis, repair loop, diagnostics rules), hence RC2. Scope policy, hash-bound approval and hidden-test isolation stay unchanged; changes are additive restrictions only.

## E. Implementation instructions
1. Write the RC2 change list and preregister the validation plan (what is exploratory, what is confirmatory) before coding.
2. Implement so RC1 can still be reproduced (RC2 condition names and code fingerprint distinct; the RC1 fingerprint check still passes for RC1 runs).
3. Validate on the **dev split** and on a **fresh blind draw** of cases untouched by the failure analysis; label every already-analysed site exploratory only. Spend only within an AxForge allowance approved by the owner (remaining RC1 allowance is in the findings doc).
4. Unit tests with the fake gateway for each fix.

## F. Checklist
- [ ] Owner approval recorded
- [ ] Change list and validation plan preregistered
- [ ] Three fixes with unit tests
- [ ] RC2 fingerprint recorded; RC1 fingerprint unchanged
- [ ] Dev and fresh-blind validation (analysed sites labelled exploratory)
- [ ] Results saved in new run directories

## G. Expected deliverables
RC2 code, new fingerprint, tests, validation results (new directories), a short note for the paper's threats to validity.

## H. Testing and validation
Fake-gateway tests: an over-long rationale is accepted and logged; an identical second patch is refused with a reason; the hostname finding yields candidate values. Acceptance: an RC1 run still reproduces from cache with the old fingerprint; no result from the 35 analysed sites is presented as confirmation.

## I. Dependencies and integration
- **Informed by:** technical-findings-2026-11-24.md sections 4, 5, 7B.
- **Depends on:** none for design; owner approval to start.
- **Runs in parallel with:** P5-S06 to P5-S08.
- **Unblocks:** P5-S11 (if the RC2 changes are included).

## J. Definition of done
RC2 validated as above and reviewed by Rafique; owner approves; RC1 untouched.
