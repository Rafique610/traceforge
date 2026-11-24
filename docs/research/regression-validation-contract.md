# Regression validation contract (P5-S17 / P5-S11, Ruhan-owned layer)

Status: implemented as an opt-in layer in `backend/traceforge/regression/`; tests in `backend/tests/regression/` (25 pass, 1 skipped without the `openai` package). No file of the RC1 fingerprint list is edited or imports it (`repair/loop.py` is read-only and is composed, not changed). Zero provider calls. Design: [root-cause-impact-regression-design.md](root-cause-impact-regression-design.md) 6.1-6.3.

## VERIFIED facts
- `run_repair(..., run_tests, max_attempts)` takes `run_tests(TestRunRequest) -> TestRunResult` (suite in `reproducer|visible|hidden`). The loop calls `visible` once per patched attempt and `hidden` once on the frozen patch. The wrapper replaces only `run_tests`.
- The request has no selected-test field, so selected tests need an injected `run_selected(req, ids) -> TestRunResult` (the sandbox adapter must support node ids; not provided here).
- Targeted failure is returned to the loop as the visible result (fast fail); the loop's own `build_feedback` then carries our text because `stdout_tail` is replaced by the regression feedback (no pytest sections, so the raw tail is used). A targeted pass continues to the full visible suite. Hidden gate untouched.
- Hidden isolation: the graph is built from the worktree, which may contain the hidden dir, so `GraphImpactProvider` filters by `hidden_paths` (prefix/glob) and by the `visible_tests` allow-list. Tested on `lab/` and a temp git repo.
- Frozen retrieval cannot be swapped inside the pipeline without a hook in `retrieval/sources.py` (RC2 follow-up, NOT implemented). `RET-*` adapters work offline and in specs only.

## Interface for Rafique (S15)
```python
class ImpactProvider(Protocol):
    name: str
    def analyse(self, base_root, patched_root, *, visible_tests: Sequence[str],
                hidden_paths: Sequence[str] = (), seeds: Sequence[str] = ()) -> ImpactReport
```
`ImpactReport` (pydantic, `regression/impact.py`): `modified_files`, `modified_symbols` (added|removed|body|signature|seed), `direct_dependants`, `transitive_dependants` (depth<=3, `path`, `via`, `evidence_class` in static|observed|inferred|unknown, `breaking`), `config_consumers`, `related_tests` (ranked, `direct`, `path`), `risk_flags`, `not_analysable`, `limitation` (fixed text `LIMITATION`), `impact_sha256` = sha256 of canonical JSON (sorted keys, compact) excluding the hash itself; use `.sealed()` / `.verify()`.
Requirements on any provider: deterministic, offline, never emit a hidden path or a test outside `visible_tests`, no secret values, `related_tests[*].test_id` in the runner's id vocabulary (graph test ids without the `test:` prefix, or file-level ids).
Plug-in: `register_impact_provider("s15", factory)` or provide `traceforge.analysis.impact_report.make_provider()`; `get_impact_provider("s15")` imports it lazily. Default name `graph`.
`select_tests(report, visible_tests, limit=None) -> Selection(tests[(test_id, reason, rank)], fallback)`: direct first, then transitive depth, ties by id; empty selection gives `fallback="full_suite"`.

## Runner and history
`RegressionAwareRunner(provider, base_root, visible_tests, run_tests, run_selected, history, hidden_paths, hidden_markers, max_attempts=3, fast_fail=True)` is a `run_tests` for the loop. `max_attempts` must be an int in 1..10 (`MAX_ATTEMPTS_CEILING`) and visible calls beyond it raise `RegressionGuardError`. `run_repair_regression_aware(..., **run_repair_kwargs)` builds the base worktree and calls `run_repair` unchanged. If the provider fails the runner degrades to the full suite and records a note. `PatchHistory(path)` appends JSONL: one `patch_version` row per attempt (attempt, patch_sha256 of the tree diff, impact_sha256, selected_tests, targeted_result, full_visible_result, outcome in targeted_failed|visible_failed|visible_passed|sandbox_error) plus one `hidden_gate` row with counts only.
Feedback (`build_regression_feedback`): visible test id, assertion lines, impact path; `LeakRefused` on hidden markers/paths, unknown test ids, the `agent.prompting.HIDDEN_MARKERS` words, or a failing optional `extra_check` (e.g. `HiddenLeakGuard.check`).

## P5-S11 support
`regression/retrieval_adapters.py`: `RET-L`, `RET-G` (and alias `RET-LG`) map to `retrieve(mode="L"|"G")`; `RET-E`, `RET-LE`, `RET-LGE` register only if `retrieval/dense.py` / `retrieval/hybrid.py` exist and expose `make_adapter(name)`. `regression/experiment.py`: `validate_preregistration(spec)` refuses unless ADR 0003 `## Decision` is `go` (today: "None yet", so refused), an approved token ceiling is recorded, arms are registered, hypotheses and the seeded case draw exist, and the run dir is new and outside `results/final`.

## Remaining for the S15 integration and RC2
- Rafique's S15 provider behind the protocol; golden fixtures for evidence classes `observed`/`inferred`, subclasses/overriders overlay (the default provider emits only static/inferred/unknown).
- A sandbox `run_selected` adapter for node ids; RC2 hook in `retrieval/sources.py` for swapping retrieval; new RC2 fingerprint if this layer is wired into the pipeline; owner approval and P5-S16 benefit evidence before any use.
