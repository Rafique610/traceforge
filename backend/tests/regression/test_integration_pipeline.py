# ruff: noqa: E501
"""Regression layer wired through the real seam (wire_regression -> run_repair), real pytest repo."""

import subprocess
from contextlib import ExitStack

import pytest
from conftest import ALLOW, CALL, DISC, HIDDEN_PATHS, run_tests

from traceforge.contracts.test_run import TestRunRequest, TestRunResult
from traceforge.regression import PatchHistory, SelectedTestRunner, wire_regression
from traceforge.regression.impact import GraphImpactProvider
from traceforge.regression.sandbox_adapter import (
    SelectedSuiteError,
    discover_visible_ids,
    regression_meta,
    resolve_provider,
)
from traceforge.repair.loop import run_repair

HIDDEN_NAMES = ["test_hidden_half", "tests/test_hidden.py"]


def go(
    repo,
    proposals,
    tmp_path,
    *,
    cond="G1",
    provider=None,
    markers=HIDDEN_NAMES,
    layer="graph",
    max_attempts=3,
):
    path, sha = repo
    seen, it = [], iter(proposals)

    def propose(ctx, fb):
        seen.append(fb)
        return next(it)

    sel = SelectedTestRunner(lambda r: run_tests(r))
    with ExitStack() as stack:
        runner = wire_regression(
            run_tests, layer=layer, repo_path=path, base_sha=sha, selected=sel, condition=cond,
            history_path=tmp_path / "patch_history.jsonl", hidden_paths=HIDDEN_PATHS,
            hidden_markers=markers, max_attempts=max_attempts, stack=stack, provider=provider,
        )  # fmt: skip
        res = run_repair(
            case_id="c", repo_path=path, base_sha=sha, condition="F" + cond[1], context="CTX",
            propose_edit=propose, run_tests=runner, allowlist=ALLOW, max_attempts=max_attempts,
        )  # fmt: skip
    return res, runner, seen, sel


def test_dependant_regression_caught_targeted_recorded_fed_back_and_repaired(repo, tmp_path):
    res, runner, seen, sel = go(repo, [DISC, DISC + "\n" + CALL], tmp_path)
    v1, v2 = runner.history.versions
    assert v1.outcome == "targeted_failed" and v1.full_visible_result is None
    assert "tests/test_checkout.py::test_total_halves" in v1.targeted_result["failing"]
    assert "tests/test_checkout.py::test_total_halves" in seen[1] and "impact path" in seen[1]
    assert v2.outcome == "visible_passed" and res.outcome == "TEST_VERIFIED_IN_LAB"
    assert runner.hidden_calls == 1 and runner.attempts == 2
    rows = PatchHistory.read(tmp_path / "patch_history.jsonl")
    assert [r["event"] for r in rows] == ["patch_version", "patch_version", "hidden_gate"]
    assert sel.container_runs == 2  # attempt 1 targeted only; attempt 2 targeted+full share one run
    meta = regression_meta("graph", runner, "patch_history.jsonl")
    assert meta["regression_layer"] == "graph" and meta["impact_provider"] == "graph"
    assert meta["regression_attempts"][0]["impact_sha256"] and not meta["impact_analysis_failed"]


def test_impact_failure_degrades_to_full_suite_with_note(repo, tmp_path):
    class Boom:
        name = "boom"

        def analyse(self, *a, **k):
            raise RuntimeError("graph build exploded")

    res, runner, seen, _ = go(repo, [DISC + "\n" + CALL], tmp_path, provider=Boom())
    (v,) = runner.history.versions
    assert v.note.startswith("impact_analysis_failed") and v.selection_fallback == "full_suite"
    assert v.targeted_result is None and v.full_visible_result["failed"] == 0  # still validated
    assert res.outcome == "TEST_VERIFIED_IN_LAB"
    assert regression_meta("graph", runner, None)["impact_analysis_failed"] is True


def test_unavailable_provider_is_recorded_not_raised(repo, tmp_path, monkeypatch):
    import traceforge.regression.sandbox_adapter as m

    def nope(name):
        raise KeyError("module not present")

    monkeypatch.setattr(m, "get_impact_provider", nope)
    p = resolve_provider("s15")
    assert p.name == "s15"
    res, runner, _, _ = go(repo, [DISC + "\n" + CALL], tmp_path, provider=p, layer="s15")
    assert runner.history.versions[0].note.startswith("impact_analysis_failed")
    assert res.outcome == "TEST_VERIFIED_IN_LAB"


def test_leak_guard_withholds_feedback_with_hidden_marker(repo, tmp_path):
    # the failing visible test id is itself a registered hidden marker -> details withheld
    res, runner, seen, _ = go(
        repo, [DISC, DISC + "\n" + CALL], tmp_path, markers=["test_total_halves"]
    )
    assert "withheld by the leak guard" in seen[1]
    assert (
        "impact path" not in seen[1] and "tests/test_hidden.py" not in seen[1]
    )  # our evidence withheld
    assert res.outcome == "TEST_VERIFIED_IN_LAB"


def test_hidden_test_never_visible_to_the_layer(repo, tmp_path):
    path, _ = repo
    assert "tests/test_hidden.py::test_hidden_half" in discover_visible_ids(
        path
    )  # in this fixture tree
    res, runner, _, _ = go(repo, [DISC + "\n" + CALL], tmp_path)
    assert all("hidden" not in t for t in runner.visible_tests)  # filtered by hidden_paths
    status = subprocess.run(
        ["git", "-C", path, "status", "--porcelain"], capture_output=True, text=True
    ).stdout
    assert status == ""


def test_f0_condition_gets_no_feedback_and_attempts_never_exceed_max(repo, tmp_path):
    res, runner, seen, _ = go(repo, [DISC] * 3, tmp_path, cond="G0")
    assert seen == [None, None, None] and runner.attempts == 3 and res.outcome == "REJECTED"
    assert runner.hidden_calls <= 1  # the gate never runs more than once
    _, runner2, seen2, _ = go(repo, [DISC] * 2, tmp_path / "b", max_attempts=2)
    assert runner2.attempts == 2 and len(seen2) == 2


def test_selected_runner_filters_and_refuses_non_visible_suites(repo):
    path, _ = repo
    calls = []

    def visible(req):
        calls.append(req.suite)
        return run_tests(req)

    sel = SelectedTestRunner(visible)
    req = TestRunRequest(case_id="c", worktree_path=path, suite="visible")
    r = sel.run_selected(req, ["tests/test_visible.py::test_zero"])
    assert [t.id for t in r.tests] == ["tests/test_visible.py::test_zero"] and r.passed == 1
    r2 = sel.run_selected(req, ["tests/test_checkout.py"])  # file-level id selects all in file
    assert r2.passed == 1 and sel.container_runs == 1  # memoised
    full = sel.run_visible(req)
    assert isinstance(full, TestRunResult) and full.passed == 3 and sel.container_runs == 1
    sel.run_visible(req)
    assert sel.container_runs == 2  # memo consumed by the full stage
    for suite in ("hidden", "reproducer"):
        with pytest.raises(SelectedSuiteError):
            sel.run_selected(req.model_copy(update={"suite": suite}), [])
    assert set(calls) == {"visible"}


def test_workdir_prefix_vocabulary_is_mapped(repo):
    path, _ = repo
    sel = SelectedTestRunner(run_tests, workdir_rel="lab/svc")
    req = TestRunRequest(case_id="c", worktree_path=path, suite="visible")
    r = sel.run_selected(req, ["lab/svc/tests/test_visible.py::test_ident"])
    assert [t.id for t in r.tests] == ["lab/svc/tests/test_visible.py::test_ident"]


def test_graph_provider_is_default_registered():
    assert isinstance(resolve_provider("graph"), GraphImpactProvider)
