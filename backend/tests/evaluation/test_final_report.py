# ruff: noqa: E501
"""Tests for the offline final-evaluation report (synthetic run directories built in tmp_path)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from traceforge.evaluation import final_report as fr

REPO = Path(__file__).resolve().parents[3]

CASES = [
    {"case_id": "c1", "cause_class": "configuration", "variant_group": "A", "service": "svc",
     "gold_symbols": [{"path": "s/settings.py", "qualname": "S.k", "start_line": 1, "end_line": 3}], "gold_config_keys": ["svc.K"]},
    {"case_id": "c2", "cause_class": "application_code", "variant_group": "B", "service": "svc",
     "gold_symbols": [{"path": "f.py", "qualname": "g", "start_line": 1, "end_line": 9}], "gold_config_keys": []},
    {"case_id": "c3", "cause_class": "application_code", "variant_group": "B", "service": "svc",
     "gold_symbols": [{"path": "f.py", "qualname": "h", "start_line": 10, "end_line": 19}], "gold_config_keys": []},
    {"case_id": "c4", "cause_class": "insufficient_evidence", "variant_group": "C", "service": "svc",
     "gold_symbols": [], "gold_config_keys": []},
]  # fmt: skip
T = {"c1": "svc.K", "c2": "f.py::g", "c3": "f.py::h", "c4": None}
DIFF = "--- a/f.py\n+++ b/f.py\n@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"


def _attempt(n, passed, fb):
    return {"n": n, "reasons": [] if passed else ["tests failed"], "has_diff": True, "visible_passed": passed,
            "counts": {"repro_passed": 1 if passed else 0, "repro_failed": 0 if passed else 1, "visible_passed": 5, "visible_failed": 0},
            "feedback_received": fb, "feedback_items": [], "visible_outcomes": {"t::a": "passed"},
            "diff_stats": {"files": {"f.py": {"removed_at": [1], "added_after": [1]}}, "added": 1, "removed": 1}}  # fmt: skip


def put(
    run,
    cond,
    cid,
    rep,
    outcome,
    attempts,
    *,
    wrong_class=False,
    fp="fp1",
    tokens=(100, 10),
    lat=1000,
):
    fixed = outcome == "TEST_VERIFIED_IN_LAB"
    abst = cid == "c4"
    cls = (
        "insufficient_evidence"
        if abst
        else (
            "runtime_dependency"
            if wrong_class
            else next(c["cause_class"] for c in CASES if c["case_id"] == cid)
        )
    )
    rec = {"run_id": run.name, "case_id": cid, "condition": cond, "provider": "axforge", "model_id": "m", "prompt_hash": "ph",
           "diagnosis": {"cause_class": cls, "target": None if abst else ("f.py::zzz" if wrong_class else T[cid]), "evidence_ids": [], "abstained": abst},
           "attempts": len(attempts), "outcome": outcome, "hidden_passed": fixed, "tokens_in": tokens[0], "tokens_out": tokens[1],
           "latency_ms": lat, "tool_calls": 2, "invalid_tool_calls": 0, "cache_hits": 0, "dataset_sha256": "ds", "replicate": rep,
           "failure_reason": None, "pipeline_version": "v5"}  # fmt: skip
    (run / "records").mkdir(parents=True, exist_ok=True)
    (run / "records" / f"{cid}.r{rep}.json").write_text(json.dumps(rec), "utf-8")
    d = run / "cases" / f"{cid}.r{rep}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "run_meta.json").write_text(
        json.dumps(
            {
                "tier": "final",
                "timings": {"model_s": 2.0},
                "code_fingerprint": {"sha256": fp},
                "diagnosis_rejected_calls": 1,
            }
        ),
        "utf-8",
    )
    (d / "repair.json").write_text(
        json.dumps({"outcome": outcome, "attempts": attempts, "hidden_passed": fixed}), "utf-8"
    )
    (d / "requests.jsonl").write_text("", "utf-8")
    for a in attempts:
        (d / f"attempt{a['n']}.diff").write_text(DIFF, "utf-8")
    (run / "meta.json").write_text(json.dumps({"run_id": run.name, "provider": "axforge"}), "utf-8")


V, R, U, N = "TEST_VERIFIED_IN_LAB", "REJECTED", "UNVERIFIED", "NO_PATCH"
a_ok = [_attempt(1, True, False)]


@pytest.fixture
def world(tmp_path):
    ds = tmp_path / "ds"
    (ds / "manifests").mkdir(parents=True)
    man = ds / "manifests" / "test.json"
    man.write_text(json.dumps(CASES), "utf-8")
    fin = tmp_path / "final"
    run = {c: fin / f"final-axforge-{c}" for c in fr.CONDS}
    put(run["L0"], "L0", "c1", 0, V, a_ok)
    put(run["L0"], "L0", "c2", 0, U, [_attempt(1, False, False), _attempt(2, False, False)])
    put(run["L0"], "L0", "c3", 0, N, [], wrong_class=True)
    put(run["L0"], "L0", "c4", 0, N, [])
    put(run["L1"], "L1", "c1", 0, V, a_ok)
    put(run["L1"], "L1", "c2", 0, V, [_attempt(1, False, False), _attempt(2, True, True)])
    put(run["L1"], "L1", "c3", 0, N, [], wrong_class=True)
    put(run["L1"], "L1", "c4", 0, N, [])
    for c in ("c1", "c2", "c3"):
        put(run["G0"], "G0", c, 0, V, a_ok, tokens=(80, 10))
    put(run["G0"], "G0", "c4", 0, N, [])
    put(run["G1"], "G1", "c1", 0, U, [_attempt(1, False, False), _attempt(2, False, True)])
    put(run["G1"], "G1", "c2", 0, V, a_ok)
    put(run["G1"], "G1", "c3", 0, V, a_ok)
    put(run["G1"], "G1", "c4", 0, N, [])
    return man, fin, run, tmp_path


def go(world, **kw):
    man, fin, _, tmp = world
    return fr.run_report(man, fin, tmp / "out", replicates=kw.pop("replicates", [0]), **kw)


def test_diagnosis_and_patch_metrics(world):
    res = go(world)
    L0, G0 = res["metrics"]["r0/L0"], res["metrics"]["r0/G0"]
    d = L0["diagnosis"]
    assert (
        d["n"],
        d["class_correct"],
        d["function_correct"],
        d["abstained"],
        d["abstain_correct"],
        d["n_insufficient"],
    ) == (4, 3, 2, 1, 1, 1)
    assert d["abstain_wrong"] == 0 and d["tool_calls"] == 8 and d["rejected_submissions"] == 4
    assert G0["diagnosis"]["function_correct"] == 3
    assert (L0["patch"]["fixed"], G0["patch"]["fixed"]) == (1, 3)
    assert res["metrics"]["r0/L1"]["diagnosis"] is None  # shared, not recomputed
    assert (
        res["metrics"]["r0/L1"]["patch"]["fixed"] == 2
        and res["metrics"]["r0/G1"]["patch"]["fixed"] == 2
    )
    assert L0["patch"]["attempts_dist"] == {0: 2, 1: 1, 2: 1}
    assert L0["patch"]["tokens_in"] == 400 and L0["patch"]["latency_ms_mean"] == 1000
    assert res["metrics"]["pooled/L0"]["patch"]["n"] == 4  # one replicate: pooled == r0
    assert res["provenance"]["pool_ok"] and res["provenance"]["all_share_one_fingerprint"]


def test_paired_and_feedback(world):
    res = go(world)
    p = res["paired"]
    f0 = p["L_vs_G"]["fixed_F0"]
    assert (f0["both"], f0["a_only"], f0["b_only"], f0["neither"]) == (1, 0, 2, 1)
    d = p["L_vs_G"]["diagnosis_function_correct_F0"]
    assert (d["both"], d["b_only"], d["neither"]) == (2, 1, 1)
    assert p["L_vs_G"]["tokens_F0"]["G_less"] == 3
    assert p["F0_vs_F1"]["fixed_armL"]["b_only"] == 1 and p["F0_vs_F1"]["fixed_armG"]["a_only"] == 1
    fb = res["feedback"]
    assert [(r["arm"], r["case"], r["f1_fixed_attempt"]) for r in fb["benefit"]] == [("L", "c2", 2)]
    assert (
        fb["benefit"][0]["f0_fixed_attempt"] is None
        and fb["benefit"][0]["feedback_received_at_pass"]
    )
    assert [(r["arm"], r["case"]) for r in fb["worse"]] == [("G", "c1")]  # F1 worse than F0
    assert fb["f1_failed_first_no_recovery"] == 1  # G c1
    assert fb["undetermined_no_attempt_data"] >= 1  # NO_PATCH records without attempts


def test_fail_to_pass_without_feedback_is_not_a_benefit(world):
    man, fin, run, tmp = world
    put(run["L1"], "L1", "c2", 0, V, [_attempt(1, False, False), _attempt(2, True, False)])
    res = go(world)
    assert res["feedback"]["benefit"] == []
    assert len(res["feedback"]["fail_to_pass_without_feedback_evidence"]) == 1


def test_missing_cells_provider_errors_and_na(world):
    man, fin, run, tmp = world
    (run["L0"] / "cases" / "c2.r1.provider_error.20260101").mkdir(parents=True)
    res = go(world, replicates=[0, 1])
    miss = {(m["cond"], m["case"], m["rep"]): m["reason"] for m in res["missing_cells"]}
    assert len(miss) == 16
    assert "provider_error artifacts: 1" in miss[("L0", "c2", 1)]
    assert miss[("G1", "c1", 1)] == "no record"
    assert res["metrics"]["r1/L0"]["patch"]["n"] == 0
    assert res["metrics"]["r1/L0"]["patch"]["provider_failures"] == 1
    md = (tmp / "out" / "results.md").read_text("utf-8")
    assert "n/a (no record)" in md and "| r1 | L0 | 0 | n/a" in md
    assert res["denominators"]["case_runs_present"]["L0"] == 4


def test_noise_between_replicates(world):
    man, fin, run, tmp = world
    put(run["L0"], "L0", "c1", 1, U, [_attempt(1, False, False)])
    res = go(world, replicates=[0, 1])
    n = res["noise"]["L0"]
    assert n["cases_with_2plus_replicates"] == 1 and n["fixed_disagree"] == 1


def test_mixed_fingerprint_refuses_pooling(world):
    man, fin, run, tmp = world
    put(run["G0"], "G0", "c1", 0, V, a_ok, fp="OTHER")
    res = go(world)
    assert not res["provenance"]["pool_ok"] and not res["provenance"]["all_share_one_fingerprint"]
    assert "code_fingerprint" in res["provenance"]["mixed"]
    assert "pooled/L0" not in res["metrics"] and "r0/L0" in res["metrics"]
    assert res["figures"] == [] and "by_cause_class" not in res["tables"]
    assert "POOLING REFUSED" in (tmp / "out" / "results.md").read_text("utf-8")


def test_strata_sites_and_controls(world, tmp_path):
    ctrl = tmp_path / "controls.txt"
    ctrl.write_text("c4\n", "utf-8")
    res = go(world, controls=ctrl)
    assert res["denominators"]["primary_cases"] == 3 and res["denominators"]["control_cases"] == [
        "c4"
    ]
    assert (
        res["metrics"]["pooled/L0"]["patch"]["n"] == 3
    )  # control excluded from primary denominator
    assert res["controls"]["L0"]["patch"]["n"] == 1 and "controls" in res["tables"]
    s = res["metrics"]["sites"]
    assert s["n_sites"] == 2 and s["cases_per_site"] == {"A": 1, "B": 2}
    assert (
        s["by_condition"]["G0"]["sites_any_fixed"] == 2
        and s["by_condition"]["L0"]["sites_any_fixed"] == 1
    )
    assert s["by_condition"]["L0"]["sites_all_runs_fixed"] == 1
    rows = {
        r[0]: r
        for r in (tmp_path / "out" / "tables" / "by_cause_class.csv")
        .read_text("utf-8")
        .splitlines()[1:]
        and [
            x.split(",")
            for x in (tmp_path / "out" / "tables" / "by_cause_class.csv")
            .read_text("utf-8")
            .splitlines()[1:]
        ]
    }
    assert "application_code" in rows and "insufficient_evidence" not in rows


def test_outputs_written(world):
    res = go(world)
    out = world[3] / "out"
    assert (out / "results.json").exists() and (out / "results.md").exists()
    assert len(res["figures"]) == 5 and all((out / f).stat().st_size > 100 for f in res["figures"])
    assert (out / "tables" / "patch_by_condition.csv").exists()
    json.loads((out / "results.json").read_text("utf-8"))


def test_historical_section(tmp_path):
    h = fr.historical_section()
    assert "NOT comparable" in h["limitations"] and h["records"] == []
    (tmp_path / "x.json").write_text(
        json.dumps(
            {"case_id": "k", "condition": "L0", "outcome": "REJECTED", "pipeline_version": "v4"}
        ),
        "utf-8",
    )
    h = fr.historical_section(tmp_path)
    assert h["pooled"] is False and h["records"][0]["case_id"] == "k"


def test_smoke_real_dev_runs(tmp_path):
    dev = REPO / "results" / "development"
    man = REPO / "datasets" / "manifests" / "dev.json"
    runs = {"L0": dev / "dev-axforge-L0-dd1-patch", "G0": dev / "dev-axforge-G0-dd1-patch"}
    if not man.exists() or not all(p.exists() for p in runs.values()):
        pytest.skip("real dev runs absent")
    res = fr.run_report(man, tmp_path, tmp_path / "out", [0], overrides=runs)
    assert res["metrics"]["r0/L0"]["patch"]["n"] > 0
    assert any(m["cond"] == "L1" for m in res["missing_cells"])
    assert (tmp_path / "out" / "results.md").exists()


def test_selection_subset(world, tmp_path):
    sel = tmp_path / "sel.json"
    sel.write_text(json.dumps({"cases": ["c1", "c2"]}), "utf-8")
    res = go(world, selection=sel)
    d = res["denominators"]
    assert (d["manifest_cases"], d["selected_cases"], d["primary_cases"]) == (4, 2, 2)
    assert {m["case"] for m in res["missing_cells"]} <= {"c1", "c2"}
    assert res["metrics"]["sites"]["n_sites"] == 2
    assert "selected subset (2 cases of 4), reduced protocol" in (
        tmp_path / "out" / "results.md"
    ).read_text("utf-8")
