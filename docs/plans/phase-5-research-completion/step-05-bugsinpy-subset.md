# P5-S05 — BugsInPy subset (optional)

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 5 |
| Task ID | P5-S05 |
| Synverk card | TRAC-27 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Low (optional; drop first if short of time) |
| Effort | 2.5 days |
| Status | NOT STARTED |
| Branch | `rafique/P5-S05-bugsinpy` |

## B. Objective
An external-validity check on **code** localization and repair using real Python bugs, reported separately from the synthetic results. It never stands in for configuration evaluation.

## C. Prerequisites
- A3 delivered; sandbox can run third-party packages (may need a per-project image).
- BugsInPy repository (`github.com/soarsmu/BugsInPy`); licence check per project.

## D. Technical background
- BugsInPy provides buggy/fixed commits and failing tests per bug. These map to `CaseManifest` with `origin="bugsinpy"`, `cause_class="application_code"`, gold symbols from the fix diff, reproducer = the bug's failing test, hidden = the project's other relevant tests.
- No Docker runtime evidence exists for these bugs; evidence is the failing test's traceback only. Report this limitation.
- Public bugs may be in the model's training data (contamination); say so.
- Security: third-party code runs only in the sandbox (no network, caps), never on the host with credentials.

## E. Implementation instructions
1. Pick 15–30 bugs from small projects that install offline in a slim image and whose failing test reproduces deterministically.
2. `datasets/external/bugsinpy/convert.py`: produce manifests + hidden tests; per-project image build script.
3. Validate red/green with the sandbox; drop non-reproducible bugs (log why).
4. Graph/retrieval on each project; E1 + G1 runs.
5. Separate results table; never pooled with synthetic numbers.

## F. Checklist
- [ ] Bug selection with reasons
- [ ] Licence check per project
- [ ] Converter and images
- [ ] Red/green validation; drop list
- [ ] E1 and G1 runs
- [ ] Separate table with contamination note

## G. Expected deliverables
`datasets/external/bugsinpy/*`, manifests, results table.

## H. Testing and validation
- Every included bug validates red/green.
- Acceptance: results shown only in their own table.

## I. Dependencies and integration
- **Depends on:** P4-S03, sandbox.
- **Feeds:** P6-S04 (threats to validity section).

## J. Definition of done
Either completed and reviewed, or explicitly dropped with a note in [DECISIONS_AND_OPEN_QUESTIONS.md](../DECISIONS_AND_OPEN_QUESTIONS.md); TRAC-27 updated accordingly.
