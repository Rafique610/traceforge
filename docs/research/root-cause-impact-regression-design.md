# Root-cause discovery, dependency analysis, change impact and regression safety — design

Date 25 Nov 2026. Status: PROPOSED (design only; no code, no model requests, no frozen data touched). Extends [retrieval-architecture-review.md](retrieval-architecture-review.md) and ADR 0003. Evidence labels: **VERIFIED** (read in code or measured here at zero tokens), **ASSUMPTION** (not measured), **TO EVALUATE** (a library or technique not tried here).

## 1. What the code already does (VERIFIED, 25 Nov, `lab/` graph via `build_graph`)

| Capability asked for | Present today | Gap |
|---|---|---|
| Typed edges | `calls`, `imports`, `reads_config`, `declares_config`, `service_env`, `service_runs`, `depends_on`, `tests_covers`, `defined_in`; each has a reverse (`REVERSE_OF`, `codeintel/config.py:6`) | **no inheritance / interface edge**; no data-flow edge |
| Reverse traversal | `impact_set()` walks reverse edges (`called_by`, `read_by`, `imported_by`, `covered_by`, `declared_by`, `env_of`), depth 3, cycle-safe, marks `breaking` for depth-1 callers of a signature-changed symbol (`queries.py:128`) | persisted for audit only (`agent/persist.py:106`); **not used for retrieval, test selection or patch acceptance** |
| Multi-hop, relevance-aware | `neighbors()` capped at 2 hops; `weighted_distances()` Dijkstra with edge weight x confidence and hub down-weighting | no per-relationship budget, no direction-aware scoring, no explanation of why a node was reached |
| Config to code | `cfg:KEY` nodes. Probe on `cfg:REDIS_HOST` returns its readers (settings field, `shop_api/app/queue.py::get_client`, `worker/queue.py::make_client`, ...) and the services that set it (`svc:shop_api`, `svc:worker`); 31 impact entries, tests included | **values are not stored**: `.env` reads key names only and compose edges carry the key, not its value (`compose_graph.py:3`). A wrong hostname or default cannot be seen |
| Code to test | `tests_covers` (confidence 1.0/0.9 for called, 0.6 for names merely referenced) | only **26 of 99** functions in `lab/` have a covering test, so test selection and regression detection are bounded by that coverage |
| Provenance | `source` in {ast, compose, settings, dotenv}, `confidence`, `file:line`; 13 `unknown:` call targets in `lab/` (confidence 0.2) | no explicit class "static / observed at runtime / inferred / unknown"; no runtime evidence in the graph |
| Stack-trace anchors | `trace_map.py` and the L arm map trace frames to chunks | frames are not recorded as "observed" edges |
| Repair validation | `repair/loop.py`: reproducer plus **whole visible suite on every attempt**, hidden gate once, `max_attempts` parameter, per-attempt records, visible regressions logged | no impact report, no targeted ordering, no regression-evidence-specific revision step |

Confidence histogram of forward edges in `lab/`: 571 at 1.0, 42 at 0.9, 4 at 0.6, 14 at 0.5, 15 at 0.2. Roughly 95 % are high confidence and about 5 % weak or unknown; the evidence classes below expose exactly that.

Consequence for the brief's example (an error in `orders.py` caused by a Redis value in `docker-compose.yml`): the **structure** is already in the graph (code, key, service). What is missing is the **value**, so a cause such as "wrong hostname" is not yet representable. That is the most valuable new fact (section 4).

## 2. Root-cause workflow (RC-flow)

Input: symptom text, trace frames, failing test id (all visible to the model today). Output: ranked candidate locations, each with a reason chain and an evidence class. Offline first; it never reads gold or hidden tests.

1. **Seed.** BM25 and (if ADR 0003 is go) dense retrieval give initial chunks; trace frames and config names in the symptom give forced anchors, as today.
2. **Expand with budgeted, typed traversal** (section 3) in both directions from each seed: callees and imports (what it depends on), callers and importers (who depends on it), config keys it reads and the services that set them, covering tests.
3. **Score candidates.** score = seed relevance x path weight. Path weight = product of edge-type prior x edge confidence x hub factor, decaying per hop, higher toward config or toward the deepest trace frame. Priors are fixed before evaluation, not tuned on the test split.
4. **Explain.** Each candidate keeps its best path as a list of (edge type, provenance, evidence class, file:line). The explanation is that list; no model-written justification.
5. **Hand off.** Top-K candidates enter the same packer and budget as today, so cost is comparable at equal tokens.

Not claimed: that this finds the root cause. It produces ranked hypotheses with a path; the model and visible tests still decide.

## 3. Bidirectional multi-hop traversal

| Question | Query | Today |
|---|---|---|
| What does X depend on | forward `calls`, `imports`, `reads_config`, `inherits` | `neighbors()` all-type, 2 hops |
| What depends on X | reverse `called_by`, `imported_by`, `read_by`, `subclassed_by` | `impact_set()` |
| Which config values affect X | forward `reads_config`, then `service_env` / `declares_config` | structure only |
| Which tests exercise X | `covered_by` | yes |
| What else could change if X changes | `impact_set` plus overlay edges | exists, unused |

Design rules:
- **Configurable depth** (default 2 for retrieval, 3 for impact), per direction, per edge type, with a node cap; stop at hubs unless the symptom names them.
- **Do not take every neighbour.** Rank frontier nodes by path weight and keep the top N per hop. Test and file nodes stay leaves, as in `impact_set`.
- **Overlay, not a graph change.** `codeintel/` is outside the RC1 fingerprint but drives the graph RC1 uses, so it is treated as frozen. New edges (inheritance, value, runtime-observed) live in a new module as an overlay merged into a **copy** of the graph; RC1 behaviour stays byte-identical.
- **Inheritance / interface edges:** AST `ClassDef.bases` resolved to in-repo classes (plus one import hop), giving `inherits` and `overrides`. External bases are `unknown`. About 1 day inside P5-S12. Protocol / ABC conformance without explicit bases is out of scope.

### Evidence classes
Every edge and candidate path carries one of:
- `static`: found by AST / compose / settings parsing (today's confidence >= 0.9);
- `observed`: seen in a runtime artifact (trace frame, log line, failing test id from a sandbox run). Only these may be described as having happened;
- `inferred`: heuristics such as `tests_covers` at 0.6, name-based call resolution, key matched by naming convention, flow through an unresolved call;
- `unknown`: `unknown:` targets, dynamic dispatch, `getattr`, string-built keys, reflection.

An `inferred` or `unknown` relation is never presented as confirmed; the impact report lists them in a separate section. The mapping from today's data is mechanical (confidence and `unknown:` prefix), so the first version needs no change to stored graphs.

## 4. Config / environment analysis and a realistic data-flow subset

Scope: stdlib `ast` plus the existing `symbols.py`. **TO EVALUATE** (not tried): `jedi` for name resolution, `libcst` scope/def-use metadata, `pycg` / `pyan` call graphs. Engines such as `pyright`, CodeQL or Semgrep taint mode are out of scope for a student project and not needed for Python-only labs.

1. **Value extraction (new).** Literal values for compose `environment:` entries, `ports`, `command`, service names; settings defaults (`Field(default=...)`, `os.getenv("X", "d")`, `os.environ.get`). `.env` stays name-only (the existing privacy rule is kept); secret-named keys are never stored; reports redact.
2. **One config chain:** env var name -> compose service entry -> settings field -> attribute read at a use site -> constructor/client argument (`redis.Redis(host=settings.redis_host)`). Constant propagation over names and attributes, **one interprocedural hop** (argument to parameter) and returns of simple wrappers (`get_client()`).
3. **Model-free checks:** hostname that matches no compose service (`lab_redis` vs `redis`); key read in code but absent from compose; key set in compose but read by nothing (e.g. `LAB_REDIS_PORT` in `lab/` has no readers); case or prefix mismatch; code default that disagrees with compose; client port vs service port. Each finding is `static` or `inferred` with file:line on both sides.
4. **Exception propagation:** only direct `raise` / `except` / re-raise within a function and one call hop, to explain why a frame in `orders.py` carries an error created elsewhere.
5. **Dependency injection:** constructor arguments of in-repo classes by one hop; FastAPI `Depends` only by the explicit parameter default. Anything else is `unknown`.

Non-goals: sound points-to analysis, dynamic imports, metaprogramming, data flow through containers, interprocedural flow beyond one hop. The subset is kept only if section 7 shows it localizes configuration root causes better than the graph alone.

## 5. Static plus dynamic evidence
Inputs already visible to the model: trace frames and exception type, log excerpts, failing visible test id, config/environment excerpts. These become `observed` marks on nodes (frame -> function, failing test -> covered functions). Observed facts re-rank and annotate; they never create a `static` edge, and a fact that does not resolve to a file and symbol stays `unknown`.

Not planned: instrumenting target code or collecting call traces in the official pipeline. A **dev-only** coverage run on fixtures may build ground truth for the evaluation; it is never given to a model.

## 6. Change-impact analysis and regression safety

### 6.1 Impact report (offline, P5-S15)
Inputs: the patch diff and the pre- and post-patch graphs (`changed_symbols()` and `signature_changes()` exist). Contents:
- modified files and symbols (added / removed / body / signature);
- direct dependants (depth 1), `breaking` for signature changes;
- transitive dependants to depth 3 with path and evidence class;
- subclasses, overriders and config consumers (overlay);
- covering tests, ranked: direct first, transitive after;
- risk flags: removed or renamed symbol still referenced; signature change with callers outside the patch; changed default or config key read elsewhere; contract changes the graph cannot see (return type, raised exception, side effect) listed as not analysed;
- not analysable: `unknown:` call sites, dynamic dispatch, symbols with no covering test ("no test coverage: this check is blind here");
- the fixed statement: dependants are those found by static analysis; absence is not evidence of none.

### 6.2 Selection and validation workflow
Selection uses only **visible** tests; the graph is built from the repair worktree, which excludes the hidden-test directory (to be asserted by a test). Workflow: minimal patch (existing scope policy) -> impact report -> selected visible tests first, then the existing full visible suite -> hidden gate once, as today -> record each patch version, impact report hash and suite results -> reject on any failure.

Honest value assessment (VERIFIED from `loop.py`): the loop already runs the **whole visible suite every attempt**, so targeted selection catches **no additional visible regressions**. Its benefits are (a) faster, more specific feedback naming the broken dependant, (b) an auditable impact record for the reviewer, (c) flagging untested dependants (information, not protection). Whether it lowers final failures is empirical.

### 6.3 Controlled revision on regression evidence
After a visible regression in a dependant, the next attempt may receive the visible failing test id and assertion excerpt plus the impact path (like visible-reproducer feedback, used once in stage 2 on `shop_api-020`). Same patch restrictions; hidden tests and outputs never enter any prompt or feedback; `max_attempts` stays configurable (today 3); every patch version is stored with its validation results for the human reviewer; human approval unchanged. This changes `repair/` and therefore belongs to RC2 (P5-S10 family), not the frozen pipeline.

## 7. Evaluation (separate from the frozen experiment)

Eight scenario families with hand-verified expected relationships (fixtures committed with a written derivation, checked by a second person; labels never derived from the tool under test):

| # | Scenario | Gold | Tests |
|---|---|---|---|
| A | root cause in same file as symptom | function | no regression vs today |
| B | root cause in another file | function / file | cross-file expansion |
| C | root cause 2 to 3 hops away | function | multi-hop value |
| D | configuration root cause (compose, settings, host/port/default) | key + file | value-flow checks |
| E | indirect call chain (wrapper, callback, constructor) | function | static call limits |
| F | patch breaks a dependant (injected regression) | broken test / symbol | impact recall, selection |
| G | misleading relationships (hub, name collision) | gold plus decoys | precision, hub control |
| H | runtime dependency static analysis cannot see | `unknown` expected | honest abstention |

Metrics: root-cause localisation (top-1/3/5, MRR); dependency recall and precision at equal token budget; affected-dependant recall and impact-report precision (hand labels plus a dev-only coverage oracle); regression-test selection recall against full-suite failures and fraction of suite selected; regression detection rate (F); false-positive impact warnings per patch; added tokens; analysis latency; end-to-end verified repair **only if** offline results justify it and the owner approves. Paired bootstrap CIs, fixed seeds, baselines = current L and G and the P5-S08 arms.

Data: new fixtures (variants of lab cases; F by injecting a known regression into a copy of lab code) and the dev split. The frozen test split and hidden tests are not used. Size is an owner decision: minimum viable 4 families x 3 cases (12), full 8 x 5 (40). Small sets give wide intervals and the report must say so.

Thresholds are preregistered per scenario in P5-S16 before any run (cross-file top-5 improvement over G on B and C by a stated margin; no loss on A; direct-dependant recall floor on F; false-positive ceiling on G). Complexity stays only if thresholds pass.

## 8. Risks and limits
- Python static analysis cannot resolve dynamic dispatch, monkeypatching, reflection or framework magic; these are reported `unknown`, not guessed.
- Recall is bounded by test coverage (26/99 functions in `lab/`) and unknown call targets (13 in `lab/`, 69 in the package).
- Expansion adds noise and tokens (existing finding: precision 4 to 6 % for G); every arm is compared at equal budget.
- Value extraction raises secret-handling risk; rules in section 4.
- A small hand-built set can overfit the design: priors are fixed first and the decisive set is held out.
- No claim of complete root-cause discovery or complete impact coverage is made anywhere.

## 9. Task split and capacity
Step documents `step-12` to `step-17` in `docs/plans/phase-5-research-completion/`. Minimum viable path: P5-S06, S07, S08 (already proposed), then S12 (traversal and ranker, no value flow), S15 (impact report on existing `impact_set`), S16 (reduced scenario set). Value flow (S13), runtime-evidence fusion (S14) and the full evaluation follow only if the MVP shows a measurable gain. P5-S17 changes the repair pipeline: Ruhan's, conditional on approval and RC2 (P5-S10).
