# P5-S15 — Change-impact report and visible-test selection

Follow-up study **Root-cause and impact analysis** (added 2026-11-25, PROPOSED, pending owner approval Q18). Design: [root-cause-impact-regression-design.md](../../research/root-cause-impact-regression-design.md) sections 6.1, 6.2, 8. Decision D37 (proposed). Zero tokens.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 15 |
| Task ID | P5-S15 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | ESSENTIAL (MVP) |
| Effort | 2.5 days (ASSUMPTION, not measured) |
| Status | NOT STARTED (proposed, pending owner approval) |
| Branch | none (commit on `main`, D33) |

## B. Objective
Produce an offline impact report from a patch diff and the pre- and post-patch graphs, and a ranked selection of **visible** covering tests.

## C. Prerequisites
- P5-S06 (harness). Can start before P5-S12; the overlay (subclasses, overriders, config consumers, evidence classes) is added when available.

## D. Technical background
- Existing building blocks: `impact_set()`, `changed_symbols()`, `signature_changes()` (design sections 1, 6.1). Today `impact_set` is persisted for audit only.
- Honest value (section 6.2, VERIFIED from `repair/loop.py`): the repair loop already runs the **whole visible suite on every attempt**, so selection catches **no additional visible regressions**. Its value is faster and more specific feedback naming the broken dependant, an auditable impact record, and flagging untested dependants (information, not protection). Whether it lowers final failures is empirical.
- Only 26 of 99 functions in `lab/` have a covering test (VERIFIED, design section 1), so selection and detection are bounded by coverage.

## E. Implementation instructions
1. New module (e.g. `backend/traceforge/analysis/impact_report.py`); no edits to `codeintel/`, `repair/` or fingerprinted files.
2. Report sections: modified files and symbols (added/removed/body/signature); direct dependants with `breaking` for signature changes; transitive dependants to depth 3 with path and evidence class; subclasses, overriders and config consumers (overlay, when available); covering tests ranked (direct first, transitive after); risk flags (removed/renamed symbol still referenced; signature change with callers outside the patch; changed default or config key read elsewhere; contract changes the graph cannot see listed as not analysed); **not analysable** (`unknown:` call sites, dynamic dispatch, symbols with no covering test: "no test coverage: this check is blind here").
3. Fixed limitation statement in every report: dependants are those found by static analysis; absence is not evidence of none.
4. Test selection from visible tests only; build the graph from the repair worktree that excludes the hidden-test directory; assert this in a test.
5. Deterministic JSON plus rendered text; report hash (sha256 of canonical JSON) for later storage by P5-S17.
6. Secret-named config values are never included.

## F. Checklist
- [ ] Report on fixtures covers all sections including "not analysable"
- [ ] Limitation statement present (golden test)
- [ ] Visible-only selection; hidden-test directory exclusion asserted
- [ ] Deterministic output and stable hash
- [ ] No edits to frozen files; fingerprint unchanged

## G. Expected deliverables
Impact report module, selection function, golden fixtures, tests.

## H. Testing and validation
- Golden tests for the report on fixture patches (signature change, removed symbol, config default change, untested dependant).
- Isolation test: no hidden-test path in graph, report or selection.
- Determinism: two runs identical bytes.
- Acceptance: selection recall against full-suite failures and fraction of suite selected, false-positive warnings per patch, via P5-S16 (scenario F, G).

## I. Dependencies and integration
- **Informed by:** design sections 6.1, 6.2, 8.
- **Depends on:** P5-S06 (optionally P5-S12 overlay).
- **Unblocks:** P5-S16 scenario F; P5-S17 (conditional).

## J. Definition of done
Reviewed by Ruhan; golden and isolation tests green; the report never claims complete impact coverage.
