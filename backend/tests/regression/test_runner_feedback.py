# ruff: noqa: E501
import pytest
from conftest import ALLOW, CALL, DISC, HIDDEN_PATHS, VISIBLE_IDS, run_selected, run_tests

from traceforge.contracts.test_run import TestOutcome, TestRunRequest, TestRunResult
from traceforge.regression import (
    GraphImpactProvider,
    LeakRefused,
    PatchHistory,
    RegressionAwareRunner,
    RegressionGuardError,
    build_regression_feedback,
    run_repair_regression_aware,
)
from traceforge.regression.feedback import LeakGuard
from traceforge.regression.impact import ImpactReport, RelatedTest


def run(repo, proposals, history, cond="F1", max_attempts=3):
    path, sha = repo
    seen = []
    it = iter(proposals)

    def propose(ctx, fb):
        seen.append(fb)
        return next(it)

    res, runner = run_repair_regression_aware(
        provider=GraphImpactProvider(), run_selected=run_selected, visible_tests=VISIBLE_IDS,
        history=history, hidden_paths=HIDDEN_PATHS, hidden_markers=["test_hidden_half", "tests/test_hidden.py"],
        max_attempts=max_attempts, case_id="c", repo_path=path, base_sha=sha, condition=cond,
        context="CTX", propose_edit=propose, run_tests=run_tests, allowlist=ALLOW,
    )  # fmt: skip
    return res, runner, seen


def test_dependant_regression_caught_by_targeted_stage_and_recorded(repo, tmp_path):
    hist = PatchHistory(tmp_path / "h" / "versions.jsonl")
    res, runner, seen = run(repo, [DISC, DISC + "\n" + CALL], hist)
    v1, v2 = hist.versions
    # attempt 1: the dependant test is selected and fails in the TARGETED stage (fast fail)
    assert "tests/test_checkout.py::test_total_halves" in v1.selected_tests
    assert v1.outcome == "targeted_failed" and v1.full_visible_result is None
    assert v1.targeted_result["failing"] == ["tests/test_checkout.py::test_total_halves"]
    assert v1.impact_sha256 and len(v1.patch_sha256) == 64
    # feedback to attempt 2: visible id + impact path only, no hidden material
    fb = seen[1]
    assert (
        "tests/test_checkout.py::test_total_halves" in fb and "impact path" in fb and "assert" in fb
    )
    assert "hidden" not in fb.lower() and "tests/test_hidden.py" not in fb
    # attempt 2 repairs the dependant: targeted green, full visible green, hidden gate ONCE
    assert v2.outcome == "visible_passed" and v2.full_visible_result["failed"] == 0
    assert v2.patch_sha256 != v1.patch_sha256
    assert res.outcome == "TEST_VERIFIED_IN_LAB"
    assert runner.hidden_calls == 1
    rows = PatchHistory.read(tmp_path / "h" / "versions.jsonl")  # human-readable JSONL, append-only
    assert [r["event"] for r in rows] == ["patch_version", "patch_version", "hidden_gate"]
    assert rows[0]["attempt"] == 1 and rows[1]["attempt"] == 2


def test_full_suite_runs_after_targeted_pass_and_hidden_still_gates(repo):
    hist = PatchHistory()
    res, runner, _ = run(repo, [DISC + "\n" + CALL], hist)
    (v,) = hist.versions
    assert v.targeted_result["failed"] == 0 and v.full_visible_result["passed"] == 3
    assert res.outcome == "TEST_VERIFIED_IN_LAB" and runner.hidden_calls == 1


def test_max_attempts_passthrough_and_no_unlimited_loops(repo):
    hist = PatchHistory()
    res, runner, seen = run(repo, [DISC] * 2, hist, max_attempts=2)
    assert len(hist.versions) == 2 and runner.attempts == 2 and len(seen) == 2
    assert res.outcome == "REJECTED"
    for bad in (0, -1, 11, None, 10**9):
        with pytest.raises(RegressionGuardError):
            RegressionAwareRunner(provider=GraphImpactProvider(), base_root=".", visible_tests=[],
                                  run_tests=run_tests, run_selected=run_selected, max_attempts=bad)  # fmt: skip
    r = RegressionAwareRunner(provider=GraphImpactProvider(), base_root=".", visible_tests=[],
                              run_tests=run_tests, run_selected=run_selected, max_attempts=1)  # fmt: skip
    r.attempts = 1
    with pytest.raises(RegressionGuardError):
        r(TestRunRequest(case_id="c", worktree_path=".", suite="visible"))


def test_provider_failure_degrades_to_full_suite(repo):
    class Boom:
        name = "boom"

        def analyse(self, *a, **k):
            raise RuntimeError("nope")

    path, sha = repo
    hist = PatchHistory()
    from traceforge.repair.loop import run_repair
    from traceforge.repair.worktree import worktree

    with worktree(path, sha) as base:
        rr = RegressionAwareRunner(provider=Boom(), base_root=base, visible_tests=VISIBLE_IDS,
                                   run_tests=run_tests, run_selected=run_selected, history=hist)  # fmt: skip
        run_repair(case_id="c", repo_path=path, base_sha=sha, condition="F0", context="x",
                   propose_edit=lambda c, f: DISC, run_tests=rr, allowlist=ALLOW, max_attempts=1)  # fmt: skip
    (v,) = hist.versions
    assert v.impact_sha256 is None and v.note.startswith("impact_analysis_failed")
    assert v.selected_tests == [] and v.full_visible_result["failed"] == 1


# ---- feedback leak guard ---------------------------------------------------------------------
def _failed(tid, tail):
    return TestRunResult(passed=0, failed=1, tests=[TestOutcome(id=tid, outcome="failed")],
                         stdout_tail=tail, duration_ms=1, timed_out=False)  # fmt: skip


REPORT = ImpactReport(related_tests=[RelatedTest(test_id="tests/test_a.py::test_a", file="tests/test_a.py",
    depth=2, direct=False, path=["func:m.py::f", "func:m.py::g", "tests/test_a.py::test_a"],
    evidence_class="static", rank=1)])  # fmt: skip
TAIL = "____ test_a ____\n>   assert g(1) == 2\nE   assert 3 == 2\n"


def test_feedback_contains_only_permitted_fields():
    g = LeakGuard(["secret_hidden_name"], HIDDEN_PATHS)
    t = build_regression_feedback(
        _failed("tests/test_a.py::test_a", TAIL), REPORT, ["tests/test_a.py::test_a"], g
    )
    assert "tests/test_a.py::test_a" in t and "assert 3 == 2" in t
    assert "func:m.py::f -> func:m.py::g -> tests/test_a.py::test_a" in t


@pytest.mark.parametrize(
    "tid,tail",
    [
        ("tests/test_hidden.py::test_x", TAIL),  # hidden test id (also not in visible list)
        (
            "tests/test_a.py::test_a",
            "____ test_a ____\n>   assert secret_hidden_name()\nE   boom\n",
        ),
        ("tests/test_a.py::test_a", "____ test_a ____\nE   see tests/test_hidden.py line 3\n"),
        ("tests/test_a.py::test_a", "____ test_a ____\nE   hidden oracle expects 5\n"),
    ],
)
def test_feedback_refuses_hidden_material(tid, tail):
    g = LeakGuard(["secret_hidden_name"], HIDDEN_PATHS)
    with pytest.raises(LeakRefused):
        build_regression_feedback(_failed(tid, tail), REPORT, ["tests/test_a.py::test_a"], g)


def test_feedback_reuses_e2e_hidden_leak_guard(tmp_path):
    HiddenLeakGuard = pytest.importorskip(
        "traceforge.agent.real_sources"
    ).HiddenLeakGuard  # needs openai
    d = tmp_path / "c1"
    d.mkdir()
    (d / "test_hidden_x.py").write_text("def test_secret_name():\n    assert 1\n")
    real = HiddenLeakGuard(tmp_path, ["c1"])
    g = LeakGuard(extra_check=real.check)
    with pytest.raises(LeakRefused):
        build_regression_feedback(_failed("tests/test_a.py::test_a", "____ test_a ____\nE   test_secret_name\n"),
                                  REPORT, ["tests/test_a.py::test_a"], g)  # fmt: skip
