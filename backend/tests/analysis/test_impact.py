# ruff: noqa: E501
import json

import pytest
from rc_helpers import FILES, VISIBLE, patched_copy, run_pytest

from traceforge.analysis.impact_report import make_provider
from traceforge.contracts.test_run import TestOutcome, TestRunRequest, TestRunResult
from traceforge.regression import (
    LIMITATION,
    ImpactProvider,
    PatchHistory,
    RegressionAwareRunner,
    get_impact_provider,
    select_tests,
)

HID = ["tests_hidden"]


def analyse(tree, patched, visible=VISIBLE, seeds=()):
    return make_provider().analyse(
        tree, patched, visible_tests=visible, hidden_paths=HID, seeds=seeds
    )


def test_registry_loads_the_real_provider_lazily():
    p = get_impact_provider("s15")
    assert isinstance(p, ImpactProvider) and p.name == "s15"
    assert type(p).__module__ == "traceforge.analysis.impact_report"


def test_signature_change_overriders_callers_breaking(tmp_path, tree):
    patched = patched_copy(
        tmp_path,
        {
            "core.py": (
                "    def helper(self, x):\n        return x\n\n\nclass Child",
                "    def helper(self, x, y):\n        return x\n\n\nclass Child",
            )
        },
    )
    r = analyse(tree, patched)
    assert r.verify() and r.limitation == LIMITATION
    assert [(m.id, m.change) for m in r.modified_symbols] == [
        ("func:core.py::Base.helper", "signature")
    ]
    assert r.modified_files == ["core.py"]
    direct = {d.id: d for d in r.direct_dependants}
    assert (
        direct["func:core.py::Base.run"].breaking
        and direct["func:core.py::Base.run"].evidence_class == "static"
    )
    assert direct["func:svc.py::GrandChild.helper"].via == "overridden_by"
    codes = {(f.code, f.subject) for f in r.risk_flags}
    assert ("signature_change_external_callers", "func:core.py::Base.helper") in codes
    assert ("signature_change_overriders", "func:core.py::Base.helper") in codes
    # transitive dependants carry the path and an evidence class
    assert any(
        d.depth == 2 and d.path[0] == "func:core.py::Base.helper" for d in r.transitive_dependants
    )
    assert all(
        d.evidence_class in ("static", "inferred", "unknown", "observed")
        for d in r.direct_dependants + r.transitive_dependants
    )
    assert any("contract changes the graph cannot see" in n.reason for n in r.not_analysable)


def test_subclasses_listed_for_a_modified_class(tmp_path, tree):
    patched = patched_copy(tmp_path, {"core.py": ("class Base:\n", "class Base(object):\n")})
    r = analyse(tree, patched)
    ids = {d.id: d.via for d in r.direct_dependants + r.transitive_dependants}
    assert (
        ids.get("class:core.py::Child") == "subclassed_by"
        and ids.get("class:svc.py::Mixin") == "subclassed_by"
    )


def test_removed_symbol_still_referenced_and_import_time_break(tmp_path, tree):
    patched = patched_copy(tmp_path, {"util.py": ("def norm(x):", "def norm2(x):")})
    r = analyse(tree, patched)
    codes = {(f.code, f.subject) for f in r.risk_flags}
    assert ("removed_symbol_still_referenced", "func:util.py::norm") in codes
    assert ("import_time_break", "func:util.py::norm") in codes
    assert [d.id for d in r.direct_dependants] == ["func:api.py::addr"]
    assert "tests/test_api.py::test_addr" in [t.test_id for t in r.related_tests]  # fails at import


def test_config_default_change_consumers_and_secret_redaction(tmp_path, tree):
    patched = patched_copy(
        tmp_path,
        {
            "cfg.py": (
                'PORT = int(os.getenv("PORT", "80"))',
                'PORT = int(os.getenv("PORT", "81"))',
            ),
        },
    )
    (patched / "cfg.py").write_text(
        (patched / "cfg.py").read_text().replace('"hunter2"', '"hunter3"'),
        encoding="utf-8",
        newline="\n",
    )
    (patched / "compose.yaml").write_text(
        FILES["compose.yaml"].replace("HOST: x", "HOST: y").replace("s3cret", "s4cret"),
        encoding="utf-8",
        newline="\n",
    )
    r = analyse(tree, patched)
    flags = {(f.code, f.subject): f.detail for f in r.risk_flags}
    assert ("config_default_changed", "cfg:PORT") in flags and "'80' -> '81'" in flags[
        ("config_default_changed", "cfg:PORT")
    ]
    assert ("config_default_changed", "cfg:HOST") in flags
    consumers = {(c.config_key, c.consumer) for c in r.config_consumers}
    assert ("cfg:PORT", "func:api.py::port") in consumers and (
        "cfg:HOST",
        "func:api.py::addr",
    ) in consumers
    text = r.canonical_json()
    for secret in ("hunter2", "hunter3", "s3cret", "s4cret"):
        assert secret not in text
    assert "[redacted]" in text


def test_not_analysable_lists_unknown_sites_and_blind_spots(tmp_path, tree):
    patched = patched_copy(
        tmp_path,
        {"svc.py": ("    return getattr(core, name)()", "    return getattr(core, name)(1)")},
    )
    r = analyse(tree, patched)
    reasons = {(n.subject, n.reason) for n in r.not_analysable}
    assert any(
        s.startswith("func:svc.py::dyn -> unknown:dynamic:") and "no in-repo candidate" in why
        for s, why in reasons
    )
    assert ("func:svc.py::dyn", "no test coverage: this check is blind here") in reasons
    patched2 = patched_copy(
        tmp_path, {"svc.py": ("    return obj.run(v)", "    return obj.run(v) + 0")}, "patched2"
    )
    r2 = analyse(tree, patched2)
    assert any("name-resolved to 2 inferred candidate(s)" in n.reason for n in r2.not_analysable)


def test_hidden_paths_never_appear_even_if_listed_as_visible(tmp_path, tree):
    patched = patched_copy(tmp_path, {"core.py": ("        return x + 1", "        return x + 2")})
    leaky_visible = [*VISIBLE, "tests_hidden/test_h.py::test_hidden_base", "tests_hidden/test_h.py"]
    r = analyse(tree, patched, leaky_visible)
    blob = r.canonical_json()
    assert "tests_hidden" not in blob and "test_hidden_base" not in blob
    # a hidden test covering Base.run exists in the tree: it is not selectable
    assert all(not t.test_id.startswith("tests_hidden") for t in r.related_tests)
    sel = select_tests(r, leaky_visible)
    assert all("hidden" not in i for i in sel.ids)


def test_only_visible_tests_are_selectable(tmp_path, tree):
    patched = patched_copy(tmp_path, {"core.py": ("        return x + 1", "        return x + 2")})
    r = analyse(tree, patched, ["tests/test_core.py::test_child"])
    assert [t.test_id for t in r.related_tests] == ["tests/test_core.py::test_child"]
    r_all = analyse(tree, patched)
    assert "tests/test_core.py::test_child" in [t.test_id for t in r_all.related_tests]
    sel = select_tests(r_all, VISIBLE)
    assert sel.ids[0] == "tests/test_core.py::test_child" and set(sel.ids) <= set(VISIBLE)
    ranks = [t.rank for t in r_all.related_tests]
    assert ranks == list(range(1, len(ranks) + 1))


def test_deterministic_bytes_and_stable_hash(tmp_path, tree):
    patched = patched_copy(tmp_path, {"core.py": ("        return x + 1", "        return x + 2")})
    a, b = analyse(tree, patched), analyse(tree, patched)
    assert (
        a.canonical_json() == b.canonical_json()
        and a.impact_sha256 == b.impact_sha256
        and a.verify()
    )
    assert not a.model_copy(update={"limitation": "x"}).verify()
    json.loads(a.canonical_json())


def test_no_change_gives_empty_report_and_full_suite_fallback(tree):
    r = analyse(tree, tree)
    assert not r.modified_symbols and not r.related_tests
    assert select_tests(r, VISIBLE).fallback == "full_suite"


def _run(req: TestRunRequest, targets) -> TestRunResult:
    passed, failed, bad = run_pytest(__import__("pathlib").Path(req.worktree_path), targets)
    return TestRunResult(
        passed=passed,
        failed=failed,
        tests=[TestOutcome(id=i, outcome="failed") for i in bad],
        stdout_tail="",
        duration_ms=1,
        timed_out=False,
    )


def test_plugs_into_regression_aware_runner(tmp_path, tree):
    patched = patched_copy(
        tmp_path,
        {
            "core.py": (
                "    def helper(self, x):\n        return x\n\n\nclass Child",
                "    def helper(self, x):\n        return x + 100\n\n\nclass Child",
            )
        },
    )
    hist = PatchHistory(tmp_path / "h" / "v.jsonl")
    runner = RegressionAwareRunner(
        provider=get_impact_provider("s15"), base_root=tree, visible_tests=VISIBLE,
        run_tests=lambda req: _run(req, ["tests/test_core.py", "tests/test_api.py", "tests/test_svc.py"]),
        run_selected=_run, history=hist, hidden_paths=HID, hidden_markers=["test_hidden_base"], max_attempts=2,
    )  # fmt: skip
    res = runner(TestRunRequest(case_id="c", worktree_path=str(patched), suite="visible"))
    v = hist.versions[0]
    assert v.impact_sha256 and len(v.impact_sha256) == 64
    assert "tests/test_core.py::test_base" in v.selected_tests
    assert v.outcome == "targeted_failed" and res.failed >= 1
    assert runner.last_report is not None and runner.last_report.provider == "s15"
    assert all(not t.startswith("tests_hidden") for t in v.selected_tests)
    with pytest.raises(Exception):  # noqa: B017  - attempts beyond max_attempts are refused
        runner(TestRunRequest(case_id="c", worktree_path=str(patched), suite="visible"))
        runner(TestRunRequest(case_id="c", worktree_path=str(patched), suite="visible"))
