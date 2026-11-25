# P5-S16 — Root-cause and impact evaluation suite

Follow-up study **Root-cause and impact analysis** (added 2026-11-25, PROPOSED, pending owner approval Q18). Design: [root-cause-impact-regression-design.md](../../research/root-cause-impact-regression-design.md) section 7 (scenario families, metrics, thresholds), section 8. Decision D37 (proposed); open question Q17 (set size). Zero tokens.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 16 |
| Task ID | P5-S16 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Rafique |
| Supporting | Muhammad Ruhan Kamran (independent verifier of hand-labelled expected relationships) |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | ESSENTIAL (MVP) |
| Effort | MVP reduced set (4 families x 3 cases) about 1.5 days; full set (8 families x 5 cases) about 3 days (ASSUMPTION, not measured) |
| Status | reduced suite IMPLEMENTED; second reviewer verification open; not reviewed, not approved |
| Branch | none (commit on `main`, D33) |

**Status sync 2026-11-25.** Evidence: `benchmarks/rootcause/` (23 fixtures: A2 B4 C4 D4 F5 G2 H2; labels hand-written; second reviewer verification open in `benchmarks/rootcause/expected_relationships.csv`), `docs/research/rootcause-impact-evaluation.md`. Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; the task stays Rafique's.

## B. Objective
Evaluate the traversal/ranker (P5-S12) and the impact report (P5-S15) offline on hand-verified fixtures, against current L/G and the P5-S08 arms, with thresholds fixed before any run. Complexity is kept only if thresholds pass.

## C. Prerequisites
- P5-S06 (harness, scorer); fixtures can be built from then on. Scoring depends on P5-S12 and P5-S15 incrementally; scenarios D and E need P5-S13, scenario H and oracle labels need P5-S14.
- Owner choice of set size (Q17) and results directory.

## D. Technical background
Families (design section 7): A same-file root cause; B cross-file; C 2 to 3 hops; D configuration (compose, settings, host/port/default); E indirect call chain; F patch breaks a dependant (injected regression into a copy of lab code); G misleading relationships (hub, name collision); H runtime dependency static analysis cannot see (`unknown` expected, honest abstention).
- Metrics: top-1/3/5 and MRR; dependency recall and precision at equal token budget; affected-dependant recall and impact-report precision; regression-test selection recall and fraction of suite selected; regression detection rate (F); false-positive warnings per patch; added tokens; analysis latency. Paired bootstrap CIs, fixed seeds.
- Small sets give wide intervals; the report must say so (12 cases is a floor, 40 is the full set).
- MVP reduced set: 4 families x 3 cases. Which 4 is a preregistration choice (suggested A, B, C, F; ASSUMPTION).

## E. Implementation instructions
1. Fixtures: variants of lab cases plus injected regressions; **separate from the frozen test split**; hidden tests and the frozen test split are not used.
2. Each fixture has a committed written derivation of expected relationships. Rafique writes; **Ruhan independently verifies** each label; labels are never derived from the tool under test.
3. Preregister (commit before any run): per-scenario thresholds (cross-file top-5 improvement over G on B and C by a stated margin; no loss on A; direct-dependant recall floor on F; false-positive ceiling on G), priors, arms, seeds.
4. Run arms through the P5-S06 harness at equal budget; paired bootstrap CIs.
5. Results under `results/retrieval/<run_id>/` unless the owner picks another directory (Q open).
6. Report pass/fail per threshold, including negative results; do not claim complete root-cause or impact coverage.

## F. Checklist
- [ ] Set size decided (Q17)
- [ ] Fixtures with derivations; Ruhan verification recorded per case
- [ ] Preregistration committed before the first run
- [ ] Results with CIs and per-family tables
- [ ] Contamination check: no frozen-split or hidden-test content
- [ ] Go/no-go note per capability (S12, S13, S14, S15)

## G. Expected deliverables
Fixtures and derivations, preregistration file, scorer additions, `results/retrieval/<run_id>/` tables, short result note.

## H. Testing and validation
- Fixture validator: every expected relationship resolves to an existing file/symbol.
- Fairness: all arms use the same packer and budget; determinism of two runs.
- Acceptance: each preregistered threshold reported pass/fail with CIs; 0 tokens; fingerprint unchanged.

## I. Dependencies and integration
- **Informed by:** design section 7.
- **Depends on:** P5-S06 (fixtures), P5-S12 and P5-S15 (scoring, incremental); P5-S13/S14 for the full set.
- **Unblocks:** P5-S17 (benefit evidence), decisions on Tier 2 tasks.

## J. Definition of done
Results reproducible from saved runs; labels verified by the second person; thresholds reported as preregistered.
