# ruff: noqa: E501
"""Unit tests for the real source adapters; `e2e`-marked tests need Docker/model and skip without."""

import shutil
from pathlib import Path

import pytest

from traceforge.agent.real_sources import HiddenLeakGuard, LabEvidenceSource, ManifestCaseSource

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "datasets/manifests/dev.json"
EVIDENCE = REPO / "runs/evidence"


def test_manifest_case_source_reads_dev_manifest():
    src = ManifestCaseSource(MANIFEST)
    assert src.get("shop_api-001").cause_class == "configuration"
    assert len(src.sha256) == 64
    with pytest.raises(KeyError):
        src.get("nope")


@pytest.mark.skipif(not (EVIDENCE / "shop_api-001.json").is_file(), reason="no saved evidence")
def test_lab_evidence_source_returns_saved_bundle_with_new_incident_id():
    case = ManifestCaseSource(MANIFEST).get("shop_api-001")
    b = LabEvidenceSource(EVIDENCE).collect("inc-x", case.service, case)
    assert b.incident_id == "inc-x" and b.items


def test_lab_evidence_source_missing_without_collector(tmp_path):
    case = ManifestCaseSource(MANIFEST).get("shop_api-001")
    with pytest.raises(FileNotFoundError):
        LabEvidenceSource(tmp_path).collect("i", case.service, case)


def test_hidden_leak_guard_blocks_hidden_names(tmp_path):
    d = tmp_path / "c1"
    d.mkdir()
    (d / "test_hidden_x.py").write_text("def test_secret_name():\n    assert 1\n")
    (d / "conftest.py").write_text("")
    g = HiddenLeakGuard(tmp_path, ["c1"])
    seen = []
    chat = g.wrap(lambda m, *a, **k: seen.append(m) or "ok")
    assert chat([{"role": "user", "content": "plain"}]) == "ok"
    with pytest.raises(AssertionError):
        chat([{"role": "user", "content": "see test_secret_name"}])
    assert "conftest.py" not in g.markers


@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker missing")
def test_real_sandbox_adapter_constructs():
    from traceforge.agent.real_sources import make_sandbox_run_tests

    assert callable(make_sandbox_run_tests(REPO, REPO / "datasets"))


def test_sandbox_config_is_chosen_by_service(tmp_path, monkeypatch):
    from traceforge.agent import real_sources
    from traceforge.faultgen.validate import SANDBOX_CFGS
    from traceforge.sandbox import make_run_tests as real_make

    seen = []
    monkeypatch.setattr("traceforge.sandbox.make_run_tests", lambda *a, **k: seen.append(k["cfg"]))
    real_sources.make_sandbox_run_tests(tmp_path, tmp_path, "worker")
    real_sources.make_sandbox_run_tests(tmp_path, tmp_path, "shop_api")
    real_sources.make_sandbox_run_tests(tmp_path, tmp_path)
    assert [c.workdir_rel for c in seen] == ["lab/worker", "lab/shop_api", "lab/shop_api"]
    assert SANDBOX_CFGS["worker"].workdir_rel == "lab/worker" and real_make


def _guard_case(tmp_path):
    h = tmp_path / "hidden" / "c1"
    h.mkdir(parents=True)
    (h / "test_hidden_behaviour.py").write_text(
        "def test_price_1():\n    assert 1\n\ndef test_price_3():\n    assert 'hidden-only'\n"
    )
    v = tmp_path / "repro"
    v.mkdir()
    (v / "test_symptom.py").write_text("def test_price_1():\n    assert 1\n")
    return tmp_path / "hidden", v


def test_guard_allows_visible_shared_test_name(tmp_path):
    hidden, vis = _guard_case(tmp_path)
    g = HiddenLeakGuard(hidden, ["c1"], [vis])
    assert g.shared_visible == ["test_price_1"]
    chat = g.wrap(lambda m, *a, **k: "ok")
    out = "FAILED test_symptom.py::test_price_1 - assert 0 == 1"
    fb = "<visible_test_feedback>" + out + "</visible_test_feedback>"
    assert chat([{"role": "user", "content": fb}]) == "ok"  # legitimate F1 feedback
    sym = (
        "[EV-0009 issue shop | runtime/observed | -] SYMPTOM failing test: "
        + out
        + chr(10)
        + "[EV-0010 log x]"
    )
    assert chat([{"role": "user", "content": sym}]) == "ok"  # legitimate symptom item


def test_guard_still_blocks_hidden_only_and_files_and_paths(tmp_path):
    hidden, vis = _guard_case(tmp_path)
    chat = HiddenLeakGuard(hidden, ["c1"], [vis]).wrap(lambda m, *a, **k: "ok")
    for leak in ("test_price_3", "test_hidden_behaviour.py", "datasets/hidden_tests/c1"):
        with pytest.raises(AssertionError):
            chat([{"role": "user", "content": f"x {leak} y"}])


def test_guard_without_visible_dirs_is_unchanged(tmp_path):
    hidden, _ = _guard_case(tmp_path)
    g = HiddenLeakGuard(hidden, ["c1"])
    assert g.shared_visible == [] and "test_price_1" in g.markers
    with pytest.raises(AssertionError):
        g.wrap(lambda m, *a, **k: "ok")([{"role": "user", "content": "test_price_1"}])


def test_guard_visible_name_in_other_dir_not_exempt(tmp_path):
    hidden, _ = _guard_case(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    (other / "test_x.py").write_text("def test_unrelated():\n    pass\n")
    g = HiddenLeakGuard(hidden, ["c1"], [other])
    assert "test_price_1" in g.markers


def test_guard_v2_shared_name_outside_a_verified_span_is_blocked(tmp_path):
    hidden, vis = _guard_case(tmp_path)
    chat = HiddenLeakGuard(hidden, ["c1"], [vis]).wrap(lambda m, *a, **k: "ok")
    for text in (
        "plain mention of test_price_1",
        "<visible_test_feedback>\nok\n</visible_test_feedback>\nthen test_price_1 outside",
        "[EV-1 log x | a/b | -] test_price_1 in a non-symptom item",
    ):
        with pytest.raises(AssertionError):
            chat([{"role": "user", "content": text}])


def test_guard_v2_hidden_only_name_blocked_even_inside_feedback_span(tmp_path):
    hidden, vis = _guard_case(tmp_path)
    chat = HiddenLeakGuard(hidden, ["c1"], [vis]).wrap(lambda m, *a, **k: "ok")
    leak = "<visible_test_feedback>\nFAILED test_price_3\n</visible_test_feedback>"
    with pytest.raises(AssertionError):
        chat([{"role": "user", "content": leak}])


def test_guard_v2_with_real_repair_feedback_text_passes(tmp_path):
    """The text the repair loop actually builds from a visible run is accepted by the guard."""
    from traceforge.agent.patch import FEEDBACK_NOTE_V5
    from traceforge.contracts.test_run import TestOutcome, TestRunResult
    from traceforge.repair.feedback import FeedbackItem

    hidden, vis = _guard_case(tmp_path)
    r = TestRunResult(
        passed=0, failed=1, duration_ms=1, timed_out=False,
        tests=[TestOutcome(id="test_symptom.py::test_price_1", outcome="failed")],
        stdout_tail="___ test_price_1 ___\n>       assert f() == 1\nE       assert 0 == 1\n",
    )  # fmt: skip
    msg = FEEDBACK_NOTE_V5.format(fb=FeedbackItem.from_run("visible", r).text)
    HiddenLeakGuard(hidden, ["c1"], [vis]).check([{"role": "user", "content": msg}])


def _frag_case(tmp_path):
    h = tmp_path / "hidden" / "c1"
    h.mkdir(parents=True)
    (h / "test_hidden_behaviour.py").write_text(
        "def test_a_hidden():\n    assert quote('staff50', 200) == 100.0\n    assert ok(1)\n"
    )
    v = tmp_path / "repro"
    v.mkdir()
    (v / "test_symptom.py").write_text(
        "def test_vis():\n    assert ok(1)\n    assert quote('x', 10) == 9\n"
    )
    return tmp_path / "hidden", v


def test_guard_fragment_detection_reports_without_blocking_by_default(tmp_path):
    hidden, vis = _frag_case(tmp_path)
    g = HiddenLeakGuard(hidden, ["c1"], [vis])
    assert g.fragments == ["assert quote('staff50', 200) == 100.0"]  # visible-shared excluded
    chat = g.wrap(lambda m, *a, **k: "ok")
    assert chat([{"role": "user", "content": "assert quote('staff50',  200)  == 100.0"}]) == "ok"
    assert g.fragment_hits == ["assert quote('staff50', 200) == 100.0"]
    assert chat([{"role": "user", "content": "assert quote('x', 10) == 9"}]) == "ok"
    assert len(g.fragment_hits) == 1


def test_guard_fragment_enforce_and_off_modes(tmp_path):
    hidden, vis = _frag_case(tmp_path)
    leak = [{"role": "user", "content": "assert quote('staff50', 200) == 100.0"}]
    with pytest.raises(AssertionError):
        HiddenLeakGuard(hidden, ["c1"], [vis], fragment_mode="enforce").check(leak)
    off = HiddenLeakGuard(hidden, ["c1"], [vis], fragment_mode="off")
    off.check(leak)
    assert off.fragments == [] and off.fragment_hits == []


def test_shared_names_in_the_models_own_words_and_the_diagnosis_lines_are_allowed(tmp_path):
    hidden, vis = _guard_case(tmp_path)
    g = HiddenLeakGuard(hidden, ["c1"], [vis])
    ok = [
        {"role": "assistant", "content": '{"rationale": "test_price_1 expects 11.10"}'},
        {
            "role": "user",
            "content": "Diagnosis: x at y\nRationale: the check test_price_1 fails\n\n<code/>",
        },
    ]
    g.check(ok)  # shared name only in assistant text and the diagnosis lines
    for bad in (
        [{"role": "user", "content": "see test_price_1 in the source"}],  # shared name elsewhere
        [{"role": "assistant", "content": "test_price_3"}],  # hidden-only name in model text
        [{"role": "user", "content": "Rationale: test_price_3 and test_hidden_behaviour.py"}],
    ):
        with pytest.raises(AssertionError):
            g.check(bad)
