# ruff: noqa: E501
import csv
import json
from collections import Counter

from traceforge.analysis import rootcause_eval as E

FAMILIES = {"A": 2, "B": 4, "C": 4, "D": 4, "F": 5, "G": 2, "H": 2}


def test_case_set_shape_and_hand_written_labels():
    cases = E.load_cases()
    assert Counter(c["family"] for c in cases) == FAMILIES
    for c in cases:
        assert c["derivation"].strip(), c["id"]  # a written derivation per case
        if c["family"] == "F":
            assert c["modified"] and c["expected_dependants"] and c["predicted_failing"] is not None
        else:
            assert c["gold"] and c["chain"] and c["primary_test"]
    rows = list(
        csv.DictReader(
            (E.REPO / "benchmarks" / "rootcause" / "expected_relationships.csv").open(
                encoding="utf-8"
            )
        )
    )
    assert {r["case_id"] for r in rows} == {c["id"] for c in cases}
    assert all(r["reviewer_verdict"] == "" for r in rows)  # left blank for the second reviewer
    assert json.loads((E.CASES_DIR / "A1" / "case.json").read_text(encoding="utf-8"))["id"] == "A1"


def test_fixtures_validate_refs_resolve_and_symptoms_really_fail():
    assert E.validate() == []  # runs each fixture's pytest for real


def test_parse_pytest_frames_and_failures():
    out = (
        "_____ test_x _____\n\ntests/test_a.py:5: in test_x\n    assert f(1) == 2\napp/m.py:3: in f\n"
        "    raise ValueError('boom')\nE   ValueError: boom\n=== short test summary info ===\n"
        "FAILED tests/test_a.py::test_x - ValueError: boom\nERROR tests/test_b.py - ImportError\n"
    )
    p = E.parse_pytest(out)
    assert p["failed"] == ["tests/test_a.py::test_x", "tests/test_b.py"]
    assert p["sections"]["test_x"]["frames"] == [("tests/test_a.py", 5), ("app/m.py", 3)]


def test_bootstrap_is_seeded_and_metrics():
    a, b = E.boot_ci([1, 0, 1, 1]), E.boot_ci([1, 0, 1, 1])
    assert a == b and a[0] <= a[1]
    assert (
        E.rc_metrics(None)["rr"] == 0
        and E.rc_metrics(3)["top3"] == 1
        and E.rc_metrics(3)["top1"] == 0
    )
    assert E.first_rank(["a", "b"], {"b"}) == 2 and E.first_rank(["a"], {"z"}) is None
    assert E.tokenize("getUserName_x")[:3] == ["get", "user", "name"]


def test_symptom_noise_is_removed():
    t = "where <function f at 0x7ff12ab> in C:/tmp/rcfix_ab12cd/repo/app.py boom"
    out = E.normalise_symptom(t)
    assert "0x7ff12ab" not in out and "rcfix_" not in out and "ab12cd" not in out and "boom" in out
