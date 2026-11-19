# P2-S02 — Code graph

## A. Task identification
| Field | Value |
|---|---|
| Phase | 2 Evidence-to-repair |
| Step | 2 |
| Task ID | P2-S02 |
| Synverk card | TRAC-13 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Normal (critical path) |
| Effort | 3 days |
| Status | NOT STARTED |
| Branch | `rafique/P2-S02-code-graph` |

## B. Objective
Build the typed, provenance-carrying graph that links runtime evidence to code and config. This is the core of the research contribution: graph retrieval (P2-S03) walks it, and `distance()` (used to label every case) is computed on it.

## C. Prerequisites
- P1-S01 (lab source). `uv add networkx pyyaml`.
- Read [ARCHITECTURE.md](../ARCHITECTURE.md#research-design).

## D. Technical background
- **Nodes:** `Module`, `Function`, `Class`, `ConfigKey`, `Service`, `Test`, `ComposeEnv`. ID format: `func:lab/worker/worker/queue.py::consume`, `cfg:worker:REDIS_HOST`, `svc:worker`, `test:lab/worker/tests/test_queue.py::test_consume`.
- **Edges** (each with `source` ∈ {ast, compose, trace, settings} and `confidence` ∈ [0,1]):
  - `DEFINES` (module → function/class), `IMPORTS` (module → module), `CALLS` (function → function; static name resolution only),
  - `READS_CONFIG` (function → config key; via `settings.X`, `os.environ["X"]`, `getenv("X")`),
  - `DECLARES_CONFIG` (settings class → config key),
  - `SERVICE_RUNS` (service → entry module), `SERVICE_ENV` (service → config key, from Compose), `DEPENDS_ON` (service → service),
  - `TESTS` (test → function, via imports/names).
- **Unresolved calls** (dynamic dispatch, `getattr`, injected callables) become edges to a node `unknown:<expr>` with `confidence=0.2`; never guess a target.
- **distance(a, b):** shortest path length over an undirected view, ignoring `unknown:` nodes; `None` if unreachable. Symptom node = function of the top in-repo trace frame, or the config key named in the error, or the failing service's entry function.

## E. Implementation instructions
1. **`codeintel/python_ast.py`:** walk `.py` files of each lab service (skip tests for definitions; index tests separately); collect modules, functions (qualname, start/end line, source hash), classes, imports (resolve relative imports), calls (`ast.Call` with `Name`/`Attribute` → resolve through the module's import table and local definitions).
2. **`codeintel/config_refs.py`:** find Pydantic `BaseSettings` subclasses → `DECLARES_CONFIG`; attribute reads on a settings instance and `os.environ`/`getenv` literals → `READS_CONFIG`.
3. **`codeintel/compose_graph.py`:** services, `depends_on`, env keys → `SERVICE_ENV`; entry command → `SERVICE_RUNS`.
4. **`codeintel/tests_map.py`:** test functions → functions they import and call → `TESTS`.
5. **`codeintel/trace_map.py`:** `symbol_at(path, line, base_sha) -> node_id | None` using function spans.
6. **`codeintel/graph.py`:** `build_graph(repo_root, base_sha) -> nx.MultiDiGraph`; cache as JSON at `.cache/graph/<base_sha>.json`; `distance(graph, a, b)`; `stats(graph)` (counts per node/edge type, unknown count).
7. **CLI** `task graph:build` (prints stats) and `task graph:distance CASE=<id>` (prints the computed distance and path).
8. **Recompute seed-case distances** and update their manifests (`distance_source: "graph"`), via the dataset tooling.
9. **Tests:** a tiny fixture package under `backend/tests/codeintel/fixture_pkg/` exercising every edge type, including one dynamic call that must become `unknown:`; trace mapping on a real lab traceback.

Edge cases: syntax error in a file → skip with a warning node; same function name in two modules → qualnames keep them distinct; circular imports → fine in a graph.

## F. Checklist
- [ ] Node and edge type definitions with ID scheme
- [ ] AST symbols, imports, static calls
- [ ] Config declarations and reads
- [ ] Compose services, env, depends_on, entry
- [ ] Test → symbol mapping
- [ ] Trace frame → symbol
- [ ] Unknown edges for unresolved calls
- [ ] `build_graph`, cache, `distance`, `stats`
- [ ] CLI tasks
- [ ] Seed manifests updated with computed distance
- [ ] Fixture-package tests for every edge type
- [ ] Stats pasted on TRAC-13

## G. Expected deliverables
New: `backend/traceforge/codeintel/{python_ast,config_refs,compose_graph,tests_map,trace_map,graph}.py`, fixture package and tests. Modified: seed manifests, `Taskfile.yml`, `README.md`. Interfaces: `build_graph()`, `distance()`, `symbol_at()`.

## H. Testing and validation
- Every edge type has at least one asserted instance in the fixture test.
- For the seed config case, `distance` ≥1 and the printed path is plausible (e.g. `queue.consume → settings.ORDER_QUEUE`).
- Acceptance: unknown-edge count reported; no edge without `source`.

## I. Dependencies and integration
- **Depends on:** P1-S01.
- **Unblocks:** P2-S03 (graph ranker), P3-S01 (distance labels), P1-S06's `get_neighbors` tool (real implementation at Sync 2), P5-S01 (deeper edges).

## J. Definition of done
Merged after Ruhan's review; tests green; seed distances computed; stats posted; TRAC-13 approved.
