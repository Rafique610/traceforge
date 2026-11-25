# Root-cause and change-impact evaluation (reduced P5-S16) — preregistration and results

Date 25 Nov 2026. Tasks P5-S12 (overlay, traversal, ranker), P5-S15 (impact report, test selection) and the reduced P5-S16 (this evaluation). The tasks stay Muhammad Rafique's; this work was done by Ruhan's session at the owner's direction and is **for Rafique's review** (and for an independent second-person check of the hand labels). Design: [root-cause-impact-regression-design.md](root-cause-impact-regression-design.md). Interface contract: [regression-validation-contract.md](regression-validation-contract.md).

Zero provider calls, zero tokens, no AxForge/BeatAPI. Nothing under `codeintel/`, `results/final`, `datasets/` or any RC1-fingerprinted file was edited. Evidence labels: **VERIFIED** (measured here), **ASSUMPTION** (not measured).

## 1. What was built

| Part | File (all new, `backend/traceforge/analysis/`) |
|---|---|
| Overlay: copy of a codeintel `Graph` + `inherits`/`overrides` (+reverses `subclassed_by`/`overridden_by`), name-resolved `calls` (inferred), dynamic-dispatch/reflection markers (unknown), evidence class on every edge, `observed` only from supplied runtime facts | `overlay.py` |
| Budgeted bidirectional traversal (forward / reverse / config / tests), per-direction depth, per-edge-type budget, node cap, top-N per hop, hub control, path weight, explanation steps, the five questions as functions | `traversal.py` |
| Root-cause ranker (seeds: frames, failing tests, symptom text, retrieval hits; gold is not a parameter) | `ranker.py` |
| `make_provider()` -> `ImpactProvider` named `s15`, loaded by `get_impact_provider("s15")` | `impact_report.py` |
| Fixed priors and budgets | `priors.py` |
| Evaluation runner | `rootcause_eval.py` |

Overlay design choices (ASSUMPTION unless tested): inheritance is resolved from `ClassDef.bases` to in-repo classes with one import hop (same file, `from x import Base`, `import m; m.Base`); a base that does not resolve in the repo and is not a Python builtin becomes an `unknown:base:` node. An `unknown:` call `x.name(...)` becomes an **inferred** `calls` edge to the in-repo methods called `name` when there are at most 4 (the unknown edge stays). `getattr`/`setattr` with a computed name, `importlib.import_module`/`__import__` with a built string, `eval`/`exec` and `globals()[...]` inside a function add an `unknown:dynamic:` edge (codeintel does not see these). `observed` is assigned only to nodes named by supplied frames/failing tests and to calls/covers edges between two such nodes; it never creates an edge. Value flow (design section 4, P5-S13) is **not** built: configuration findings are keys and their declaring sources, never values.

Impact provider (S15) beyond the existing `GraphImpactProvider`: dependants come from the overlay (subclasses via `subclassed_by`, overriders via `overridden_by`, name-resolved callers as `inferred`); config changes are detected by diffing `getenv(..., default)` literals and compose `environment:` values (secret-named values are redacted; `.env` is never read); a removed or renamed symbol also yields `import_time_break` (importing files fail at load, so every test in them fails even if it never calls the symbol); risk flags `signature_change_external_callers`, `signature_change_overriders`, `removed_symbol_still_referenced`, `import_time_break`, `config_default_changed`, `config_key_read_elsewhere`; `not_analysable` lists unknown call sites (with "name-resolved to N inferred candidate(s)" or "no in-repo candidate"), contract changes and symbols with no covering visible test. Hidden paths are removed from the graph copy before any traversal and again from every entry; a test is selectable only if it is in `visible_tests`. The report is sealed with `impact_sha256` and carries the fixed limitation text.

## 2. Fixtures (23 cases, hand-written)

`benchmarks/rootcause/` (templates, cases, generator, committed trees, `expected_relationships.csv` for the second reviewer, `derivations.md`). Two lab-style mini projects (S "shop", L "ledger"), each with a green visible suite, a hidden test directory and a compose file; each case is a text edit of a clean project listed in `cases.py`. **Counts:** A 2, B 4, C 4, D 4, F 5, G 2, H 2 (family E, indirect call chains, is not in this reduced set: no value-flow, P5-S13 not built).

Every expected relationship (`chain`, `gold`, `decoys`, `expected_dependants`, `expected_direct`, `expected_flags`, `predicted_failing`) was written by hand from the template source and the edit, with a derivation note per case, **before** any tool run, and is not derived from tool output. Validator (VERIFIED, `python -m traceforge.analysis.rootcause_eval --validate-only`): every referenced symbol/key resolves in the tree, the symptom test really fails on the buggy tree (A-D, G, H), the base suite is green (F). The second-person verification of the labels is **not done** (CSV columns `reviewer_verdict`/`reviewer_note` are empty); until then the labels are single-author.

What each family means here (counted by hand in the derivations): A the failing test calls the buggy function or the cause is in the same file; B the cause is one call hop away in another file (B4 is a shared-state defect with no call edge: hard by construction); C two to three call hops; D a configuration key (compose value, settings default, renamed key, compose limit); F an injected patch on a green tree (signature change, behaviour change, rename, compose value, base-class signature with an overriding subclass); G a hub (one helper with 15 callers) and a same-name function in another module; H a dictionary dispatch and an `importlib` plugin that static analysis cannot follow (expected: report `unknown`, abstain).

**Observed runtime facts are real:** for A-D, G, H the tool is given the frames, failing test id and message of the primary symptom test **as printed by actually running the fixture's pytest** (`--tb=short`). For F the true failing set is obtained by running pytest on the clean and the patched tree; a collection error on a file counts as every test of that file failing.

## 3. Arms and metrics

Root cause arms (candidate universe: functions, methods, classes, config keys; top-20 each; same seeds where a seed is used):

| Arm | Description |
|---|---|
| `RC-overlay` | the P5-S12 ranker (overlay, traversal, priors) |
| `RC-overlay+bm25` | same, with the top-3 BM25 chunks added as retrieval seeds |
| `G-distance` | the existing codeintel `weighted_distances` (hub-penalised Dijkstra, weight x confidence) on the **original** graph from the same seeds: graph distance, no overlay, no evidence classes, no direction priors, no per-hop budget |
| `BM25` | plain Okapi BM25 over chunks (path + qualified name + source of each function/class/config key), query = the symptom text, no seeds |

Impact arms: `IMP-overlay` (S15), `IMP-graph` (the existing `regression.GraphImpactProvider` on `impact_set`), `BM25-select` (BM25 of the diff text over test chunks, selecting as many tests as `IMP-overlay` selected: equal k), `full-suite` (reference).

Metrics: top-1/3/5 and MRR against the hand-written acceptable root-cause nodes (a function id or a `cfg:KEY`); dependency recall and precision of the ranked list packed to an **equal cap of 600 approximate tokens** (cost per node = 12 + `approx_tokens` of its first 24 lines, same for every arm; expected set = hand-written chain + extra dependencies + gold); decoys in the top 5; abstention (the ranker abstains when a seed has an unresolved dynamic call site that name resolution cannot bound; baselines never abstain); affected-dependant recall and impact-report precision (reported dependants vs the hand-written list); direct-dependant recall; regression-test selection recall against the **measured** failing tests; fraction of the suite selected; detection (at least one true failing test selected); false-positive warnings (risk flags not in the hand-written expected flags, per patch); report tokens (`approx_tokens` of the canonical JSON); latency; determinism (two complete runs, identical result digest). Paired bootstrap 95% intervals (10 000 resamples, seed 20261125) for RC minus baseline differences; with n = 8 or 16 they are wide and are reported, not decisive.

## 4. Preregistration (written before the first scored run)

Frozen artefacts (sha256 at the time of writing):

| Artefact | sha256 |
|---|---|
| `analysis/priors.py` | `290be1d1dca2876275aa61cdb4bf6452717f9f2910ed471d714c37410d0fe391` |
| `analysis/rootcause_eval.py` | `9fe3496e7b12a5baaba1576f1e7e2b07bbbe434a7214af827e859aa7671ba8c6` |
| `analysis/overlay.py` | `0afe89899d50bac9dd89f1a9a5b7478f3d640a327472fd9fd0da4ac827c7c472` |
| `analysis/traversal.py` | `f26b2e45a3c948c0078c981e0cbbd41cc86ce9cf614085af1d440ff5b07ac23e` |
| `analysis/ranker.py` | `d32efb7234e43e51e7d7898c3fb6c9299334287109773f63d111be220570d1a9` |
| `analysis/impact_report.py` | `df1f9875efa4b4f378c00b8b94fb4c982fdec48a1de4c44c50a6708967791f1b` |
| `benchmarks/rootcause/` (507 files: trees, cases, CSV, derivations, templates) | `9a54013331fb0cc488af80be0efd0d075f7b500159c77137f8ebe26db9f3d04e` |

Priors (in `priors.py`, not tuned on any evaluation data): edge priors (calls 1.0, called_by 0.8, reads_config 1.0, read_by 0.7, inherits/overrides 0.7, subclassed_by/overridden_by 0.6, imports 0.4, imported_by 0.3, covered_by 0.5, env_of/declared_by 0.9), decay 0.75 per hop, direction prior forward 1.0 / config 1.0 / reverse 0.5, ranker depth forward 3 / reverse 2 / config 2, top 12 per hop, node cap 150, hub stop at degree 12, undeclared-key boost 1.25. Seeds: frame 1.0 (innermost source frame) or 0.8, failing test 0.8, symptom name match 0.7 divided by the number of same-name nodes, key-word overlap 0.5 x fraction, retrieval 0.6 x score.

**Disclosure of order (honest record).** The overlay, traversal, ranker, provider and unit tests were written first. Two constants changed during implementation against unit tests on a synthetic project (not against any case): decay is now applied once per hop (before that a one-hop cause scored equal to its seed). During development the impact provider was run once on `F1`-`F5` and its report fields were printed (so the **S15 thresholds below are not blind to that output**); the ranker and the three baselines were **never** run on any case before this section was written, and no case result was used to set any threshold. If a later code change is needed after the run, it is listed in section 6 with the re-run result.

| # | Threshold (pass/fail, point estimates; no threshold is decided by a confidence interval) |
|---|---|
| R1 | A (n=2), no loss: `RC-overlay` top-1 >= `G-distance` top-1 and MRR >= `G-distance` MRR, and gold in the top 3 of both A cases |
| R2 | B+C (n=8), cross-file gain: `RC-overlay` top-5 rate >= `G-distance` top-5 rate + 0.125 (at least one more case) **and** `RC-overlay` top-5 >= 6/8 |
| R3 | B+C: `RC-overlay` top-5 >= `BM25` top-5 |
| R4 | D (n=4): `RC-overlay` gold config key in the top 3 for >= 3/4 |
| R5 | A,B,C,D,G pooled (n=16), equal 600-token cap: `RC-overlay` macro dependency recall >= `G-distance` **and** macro precision >= `G-distance` |
| R6 | G (n=2): gold in the top 3 for both and mean decoys in the top 5 <= 1.0 |
| R7 | H (n=2): abstains on both; false abstention on the 16 non-H root-cause cases <= 1 |
| R8 | F (n=5): macro selection recall against measured failures >= 0.90 **and** detection 5/5 |
| R9 | F: macro fraction of the visible suite selected <= 0.75 (full suite = 1.0) |
| R10 | F: macro direct-dependant recall >= 0.90 and macro affected-dependant recall >= 0.80 |
| R11 | F: macro impact-report precision >= 0.70 |
| R12 | F: mean false-positive warnings per patch <= 1.0 |
| R13 | Hidden isolation: 0 hidden-path strings in any report of any arm (also unit-tested) |
| R14 | Determinism: two complete runs give an identical result digest |
| R15 | Latency: `RC-overlay` (graph + overlay + ranking) median <= 2000 ms per case, max <= 5000 ms |
| R16 | `IMP-overlay` selection recall >= `BM25-select` selection recall at equal k (informational comparison, not a gate) |

Informational (no threshold): how many of the five hand-predicted failing sets equal the measured ones; per-family tables; `RC-overlay+bm25`; `IMP-graph`; report tokens.

Decision rule per capability (complexity is kept only if it passes): **S12 go** iff R1, R2, R3 and R14; **S15 go** iff R8, R10, R13 and R14; R4-R7, R9, R11, R12, R15 are quality findings reported either way and do not block by themselves. Any "go" means "worth continuing to the next evaluation stage", not a claim of superiority.

Small-n caveat, fixed in advance: 23 cases from two toy projects written by the same hand as the tool; one case moves a family rate by 25-50 points; the fixtures are in-distribution for the tool's design (the author knew which relationships are static-visible). The result cannot support a claim about real repositories, only about whether the mechanism works at all on controlled cases.

## 5. Results

Run: `python -m traceforge.analysis.rootcause_eval` then `python -m traceforge.analysis.rootcause_verdicts` (post-processing only; it applies the table in section 4). Outputs in `results/analysis/rootcause-eval/`: `summary.json`, `cases.json` (per case and arm: top-10 lists, reason chain of the top candidate, abstention reasons, measured failures), `rootcause_metrics.csv`, `impact_metrics.csv`, `verdicts.json`, `summary.md`. 23 cases, 0 invalid. Zero provider calls. The result digest (everything except timings) is `6d6a5bd34dee24a4...` in the committed run and in every later complete run (section 6).

### 5.1 Preregistered thresholds: pass/fail

| # | Result | Measured (point estimates; n is small) |
|---|---|---|
| R1 A no loss, gold in top 3 | **FAIL** | top-1 0.50 vs 0.50 and MRR 0.60 vs 0.60 (equal to `G-distance`), but A2 ranks the cause 5th (A1: 1st) |
| R2 B+C cross-file gain over G | **FAIL** | RC top-5 0.50 vs G 0.625 (difference -0.125, bootstrap 95% [-0.375, 0.0]); absolute 4/8, 6/8 needed |
| R3 B+C not below BM25 | PASS | top-5 0.50 vs BM25 0.375 (difference +0.125, CI [-0.375, 0.625]) |
| R4 D key in top 3 | PASS | 4/4 (G-distance 3/4, BM25 0/4) |
| R5 dependency recall and precision at 600 tokens | **FAIL** | recall 0.966 vs 0.988, precision 0.379 vs 0.380 (a loss on recall, a tie on precision); BM25 0.903 / 0.250 |
| R6 G gold in top 3, decoys <= 1.0 | PASS | ranks 3 and 1; mean decoys in the top 5 = 1.0 (exactly at the ceiling) |
| R7 H abstain / false abstain | PASS | 2/2 abstain, 0/16 false abstentions |
| R8 F selection recall, detection | PASS | recall 1.00, 5/5 detected |
| R9 F suite fraction | PASS | 0.575 macro (F1 0.50, F2 0.79, F3 0.73, F4 0.50, F5 0.36) |
| R10 F dependant recall | PASS | direct 1.00, affected 1.00 |
| R11 F impact precision | PASS | 1.00 |
| R12 F false-positive warnings | PASS | 0.0 per patch |
| R13 hidden isolation | PASS | 0 hidden strings in any report (also unit-tested) |
| R14 determinism | PASS | two passes identical in the committed run and in 2 further invocations after a harness fix (section 6); the digest is the same before and after the fix |
| R15 latency | PASS | RC median 37 ms, max 106 ms per case (graph build included); BM25 6 ms, G 2 ms (ranking only) |
| R16 (informational) vs BM25 test selection at equal k | PASS | recall 1.00 vs 0.54 |

**Go / no-go by the preregistered rule: S12 (traversal and ranker) no-go; S15 (impact report and selection) go on this controlled set.**

### 5.2 Root-cause ranking (means; n per family in brackets)

Cells are top-1 / top-3 / top-5 / MRR.

| Family | RC-overlay | G-distance | BM25 |
|---|---|---|---|
| A (2) | .50 / .50 / 1.0 / .60 | .50 / .50 / 1.0 / .60 | .50 / .50 / 1.0 / .60 |
| B (4) | .25 / .50 / .75 / .48 | .25 / .50 / 1.0 / .49 | 0 / .25 / .50 / .23 |
| C (4) | 0 / 0 / .25 / .14 | 0 / 0 / .25 / .13 | 0 / 0 / .25 / .12 |
| D (4) | .50 / 1.0 / 1.0 / .75 | 0 / .75 / .75 / .37 | 0 / 0 / .75 / .20 |
| G (2) | .50 / 1.0 / 1.0 / .67 | .50 / .50 / .50 / .58 | .50 / .50 / .50 / .56 |
| H (2) | 0 / 0 / 0 / 0 (abstains) | 0 / 0 / 0 / 0 | 0 / 1.0 / 1.0 / .50 |

Per-case rank of the cause (RC / G-distance / BM25): A1 1/1/1, A2 5/5/5, B1 2/2/14, B2 1/1/2, B3 4/5/11, B4 6/4/4, C1 19/17/5, C2 5/5/12, C3 6/6/9, C4 8/9/12, D1 2/2/4, D2 1/3/4, D3 1/2/4, D4 2/7/15, G1 3/6/8, G2 1/1/1; H1 and H2 not found by RC or G (BM25 2 and 2; RC+bm25 2 and 3). Pooled over A-D and G (n=16) the paired bootstrap on MRR gives RC minus G = +0.10 [+0.01, +0.22] and RC minus BM25 = +0.22 [+0.09, +0.36]; on top-5 the intervals contain zero. This is a descriptive remark on 16 hand-built cases, not a result about repositories.

What the numbers say and do not say:
- On call-chain cases (A-C) the overlay ranker is **indistinguishable from the existing graph-distance ranking** (B1, C2, C3 identical ranks; B3, C4 one place better, B4 two places worse, C1 two worse). The structure it adds (inheritance, evidence classes, direction priors) does not help when the cause is one of several sibling callees: the graph has no information to prefer `tax` over `net_price` under `gross` (A2). In C1 the failing test's other covered helpers (`Stock.__init__`, `Stock.add`) take relevance and the three-hop cause `apply_pct` ends 19th. Assertion failures carry almost no symptom text (the only frame is the test itself), so structure alone ranks. On C no arm gets more than 1 of 4 in the top 5.
- The gains are **configuration (D)** and the **hub (G1)**: the config direction, the undeclared-key boost and hub non-expansion put the key or the cause 1 to 5 places higher than `G-distance` (D2 3 to 1, D4 7 to 2, G1 6 to 3). D1 (a wrong compose value) is solved only at the level of the key, as designed (no value flow).
- **H**: the ranker found neither cause and abstained on both, naming the unresolved dynamic call site (`HANDLERS[event['kind']]`, the `importlib.import_module` call). The baselines cannot abstain and listed non-cause candidates; BM25 ranked the plugin chunk 2nd because the test text names it, which is lexical luck, not dependency knowledge.
- `RC-overlay+bm25` adds the top-3 BM25 chunks as seeds; it changes no family's top-5 and costs precision at the token cap.

### 5.3 Change impact (family F; macro over 5 patches; true failures by running pytest)

| Arm | selection recall | suite fraction | patches detected | affected-dependant recall | impact precision | FP warnings/patch |
|---|---|---|---|---|---|---|
| IMP-overlay (S15) | 1.00 | 0.575 | 5/5 | 1.00 | 1.00 | 0.0 |
| IMP-graph (existing `GraphImpactProvider`) | 0.60 | 0.348 | 4/5 | 0.55 | 1.00 | 0.0 |
| BM25-select (equal k) | 0.54 | 0.575 | 5/5 | n/a | n/a | n/a |
| full suite | 1.00 | 1.00 | 5/5 | n/a | n/a | n/a |

The five hand-predicted failing sets equalled the measured ones (5 of 5). The existing default provider misses what the overlay adds: a config-value change (F4: 0 tests selected), an overrider and a name-resolved caller (F5), import-time breakage after a rename (F3). That shows what the extra signals contribute **on these fixtures**; it is not a statement about the default provider elsewhere. The cost is selectivity: a body change to the shared helper `round_money` selects 11 of 14 tests for 1 true failure (F2); the selection is a safe superset, not a precise one. Report size averages about 970 approximate tokens (IMP-graph 650).

### 5.4 Limits that apply to every number above

- **In-distribution fixtures.** One author wrote the tool, the projects and the labels; test functions bind typed local variables, which gives the graph `tests_covers` edges. In a unit test with a chained `Child().run(1)` the covering edge is missing and that test would not be selected: recall is bounded by what the static graph sees (the design recorded 26 of 99 functions covered in `lab/`).
- **Static analysis only.** Dynamic dispatch, reflection, monkeypatching, framework magic and contract changes (return type, raised exception, side effect) are not analysed; they appear as `unknown` / `not_analysable`, never as inferred facts. Absence from a report is not evidence of no dependants.
- **Unknown targets** limit traversal: name-resolved calls are `inferred` and capped at 4 candidates; a call through a parameter whose method name is shared by more than 4 methods stays unknown.
- **Test-coverage bound** on selection and regression detection (above).
- **No values**: configuration findings are keys and sources; a wrong host name is found only as its key.
- 23 cases, one author, one label pass: the second-person verification of `expected_relationships.csv` is open. No superiority claim is made, and nothing here is an end-to-end repair result (no model was called).

## 6. Deviations, disclosures and what changed after the preregistration

- `priors.py`, `overlay.py`, `traversal.py`, `ranker.py`, `impact_report.py` and the fixtures were not changed after the hashes of section 4 were recorded; `rootcause_eval.py` changed once, after the committed run (the determinism fix below). `rootcause_verdicts.py` (applies the table) and sections 5 and 6 were written afterwards.
- **Harness determinism defect, found and fixed after the committed numbers existed.** Early full invocations occasionally printed `deterministic: false`. Cause (found by diffing `cases.json` of two invocations): the symptom text fed to BM25 and to symptom seeding was the raw pytest section, which contains memory addresses (`at 0x...`) and the random temporary directory name; their digits and fragments became query tokens (for example `11` matched `tag_11` in G1) and changed only the **BM25 baseline** ranking among the identical `tag_NN` chunks of G1 (rank 8 or 9). Fix: `normalise_symptom` strips addresses and temp names (`rootcause_eval.py` sha256 is now `eb6af86b677b0e7cbbe62a72b1604452f9e3ea5a6c4610efdda4b612b5b3af4c`; all other hashes of section 4 unchanged). After the fix three complete invocations (six passes) are identical and their result digest equals the digest of the pre-fix committed run, so **no reported number changed**; the pre-fix and post-fix per-case results were diffed and are equal. The change is a bug fix to the harness, not a tuning step; it was made after seeing results, which is why it is recorded here.
- A lint warning (`RuntimeFacts` imported but unused in `ranker.py`) and long lines remain: editing the frozen files would invalidate the recorded hashes.
- The regression layer's contract test `backend/tests/regression/test_impact_selection.py::test_protocol_and_registry` asserted that `get_impact_provider("s15")` raises `KeyError` while the S15 module was absent. With `traceforge.analysis.impact_report.make_provider` present that assertion fails (the other 25 tests in `tests/regression` pass). The test needs a one-line update by its owner; I did not edit it.
