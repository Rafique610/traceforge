# ruff: noqa: E501
"""Validator decision logic with a FAKE runner (isolated unit test; the real-sandbox run is test_real_validation)."""

from pathlib import Path

from traceforge.contracts.test_run import TestOutcome, TestRunResult
from traceforge.faultgen.validate import load_cases, validate_case


def _result(passed: bool, n: int = 2) -> TestRunResult:
    out = "passed" if passed else "failed"
    return TestRunResult(
        passed=n if passed else 0,
        failed=0 if passed else n,
        tests=[TestOutcome(id=f"t{i}", outcome=out) for i in range(n)],
        stdout_tail="",
        duration_ms=1,
        timed_out=False,
    )


def fake_factory(marker: str, flaky: bool = False, reproduces: bool = True):
    """Red on reproducer/hidden iff the tree is mutated (marker text present in the tree)."""
    calls = {"n": 0}

    def factory(tree: Path):
        mutated = any(marker in p.read_text("utf-8") for p in (tree / "lab").rglob("*.py"))

        def run(req):
            calls["n"] += 1
            if flaky and mutated and req.suite == "reproducer" and calls["n"] % 2:
                return _result(True)
            if mutated and req.suite != "visible":
                return _result(not reproduces)
            return _result(True)

        return run

    return factory


def _case(datasets, cid):
    return next(c for c in load_cases(datasets) if c.manifest.case_id == cid)


def test_good_case_passes(datasets):
    rep = validate_case(_case(datasets, "shop_api-002"), fake_factory("lt=100"), live=False)
    assert rep.passed, rep.problems
    assert rep.checks["gold_fix_hidden"] == "green"


def test_fault_not_reproduced_is_rejected(datasets):
    rep = validate_case(
        _case(datasets, "shop_api-002"), fake_factory("lt=100", reproduces=False), live=False
    )
    assert any("fault not reproduced" in p for p in rep.problems)


def test_flaky_case_is_rejected(datasets):
    rep = validate_case(
        _case(datasets, "shop_api-002"), fake_factory("lt=100", flaky=True), live=False
    )
    assert any(p.startswith("flaky:") for p in rep.problems)


def test_manifest_drift_is_reported(datasets, lab_copy):
    (lab_copy / "shop_api" / "app" / "pricing.py").write_text("# drifted\n")
    rep = validate_case(
        _case(datasets, "shop_api-004"), fake_factory("zzz"), lab=lab_copy, live=False
    )
    assert any("base_sha drift" in p for p in rep.problems)


def test_non_repairable_case_runs_one_tree(datasets):
    rep = validate_case(_case(datasets, "shop_api-004"), fake_factory("zzz"), live=False)
    assert rep.passed, rep.problems
    assert "broken_tree" in rep.checks
