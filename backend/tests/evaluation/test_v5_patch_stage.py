# ruff: noqa: E501
"""dev-d1 patch stage: frozen inputs, saved diagnoses, diff facts, scoring and isolation."""

import json
from types import SimpleNamespace as N

import pytest
from test_eval_runner import QUIET, SAMPLES, fake

from traceforge.evaluation import freeze_manifest as fm
from traceforge.evaluation import patch_eval, runner
from traceforge.evaluation.real_run import make_real_run_fn
from traceforge.repair.diffstats import changed_lines, diff_stats

DIFF = """diff --git a/lab/shop_api/app/orders.py b/lab/shop_api/app/orders.py
--- a/lab/shop_api/app/orders.py
+++ b/lab/shop_api/app/orders.py
@@ -10,7 +10,7 @@
 def order_total(items):
     total = 0
-    for item in items[:-1]:
+    for item in items:
         total += item.price
     return total
"""


# --- diff facts -------------------------------------------------------------------------------


def test_diff_stats_reports_files_counts_and_base_lines():
    st = diff_stats(DIFF)
    f = st["files"]["lab/shop_api/app/orders.py"]
    assert (st["added"], st["removed"]) == (1, 1)
    assert f["removed_at"] == [12] and f["added_after"] == [12]  # 10 +def, 11 total, 12 the loop
    assert changed_lines(DIFF) == {
        "lab/shop_api/app/orders.py": (["for item in items[:-1]:"], ["for item in items:"])
    }


# --- frozen manifest --------------------------------------------------------------------------


def test_frozen_manifest_detects_any_change_and_refuses_to_overwrite(tmp_path, capsys):
    run = tmp_path / "results" / "run"
    run.mkdir(parents=True)
    (run / "a.json").write_text("one", "utf-8")
    (run / "b.json").write_text("two", "utf-8")
    m = fm.build([run], [], tmp_path)
    assert m["n_files"] == 2 and fm.verify_all(m, tmp_path) == []
    (run / "a.json").write_text("changed", "utf-8")
    assert fm.verify_all(m, tmp_path) == ["changed or missing: results/run/a.json"]
    (run / "c.json").write_text("new", "utf-8")
    assert fm.verify_files(m, [run / "c.json"], tmp_path) == ["not frozen: results/run/c.json"]
    out = tmp_path / "m.json"
    argv = ["build", "--out", str(out), "--dir", str(run), "--root", str(tmp_path)]
    assert fm.main(argv) == 0
    with pytest.raises(SystemExit, match="never overwritten"):
        fm.main(argv)


# --- the runner refuses unsafe patch-stage combinations ---------------------------------------


def _argv(tmp_path, *extra):
    return [
        "--manifest", "m.json", "--condition", "L0", "--run-id", "dev-x",
        "--out", str(tmp_path / "development"), "--split", "dev", *extra,
    ]  # fmt: skip


def test_patch_from_needs_v5_an_existing_run_and_no_diagnose_only(tmp_path):
    src = tmp_path / "diag"
    src.mkdir()
    assert runner.main(_argv(tmp_path, "--patch-from", str(src))) == 2  # v4
    assert (
        runner.main(_argv(tmp_path, "--pipeline", "v5", "--patch-from", str(tmp_path / "no"))) == 2
    )
    assert (
        runner.main(
            _argv(tmp_path, "--pipeline", "v5", "--patch-from", str(src), "--diagnose-only")
        )
        == 2
    )


def test_a_resumed_run_cannot_change_its_diagnosis_source(tmp_path):
    cases = []
    for i in range(2):
        c = json.loads((SAMPLES / "case_manifest.code.json").read_text("utf-8"))
        c.update(case_id=f"case-{i}", split="dev")
        cases.append(c)
    man = tmp_path / "data" / "manifest.json"
    man.parent.mkdir()
    man.write_text(json.dumps(cases), "utf-8")
    kw = dict(provider="axforge", model="glm-5.3-flash", pipeline="v5")
    runner.run_experiment(
        man,
        "L0",
        "dev-p",
        fake(),
        tmp_path / "development",
        1,
        "dev",
        **QUIET,
        **kw,
        extra_meta={"patch_from": "A"},
    )
    with pytest.raises(ValueError, match="different stage/source"):
        runner.run_experiment(
            man,
            "L0",
            "dev-p",
            fake(),
            tmp_path / "development",
            1,
            "dev",
            **QUIET,
            **kw,
            extra_meta={"patch_from": "B"},
        )


# --- saved diagnosis: loaded from a frozen run, never regenerated -------------------------------


def make_saved_run(tmp_path, *, condition="L0", abstained=False):
    root = tmp_path / "repo"
    (root / "datasets" / "manifests").mkdir(parents=True)
    (root / "datasets" / "manifests" / "dev.json").write_text("[]", "utf-8")
    run = root / "results" / "development" / "dev-axforge-L0-dd1-l1"
    d = run / "cases" / "shop_api-096.r0"
    d.mkdir(parents=True)
    (run / "records").mkdir()
    diag = {"cause_class": "insufficient_evidence"} if abstained else {
        "cause_class": "application_code", "path": "lab/shop_api/app/orders.py", "qualname": "order_total",
        "supporting_evidence_ids": ["EV-0001"], "observed_symptom": "totals skip the last line",
        "rationale": "loop skips the last item", "confidence": "low",
    }  # fmt: skip
    (d / "diagnosis.json").write_text(json.dumps(diag), "utf-8")
    item = {
        "id": "EV-0001",
        "kind": "issue",
        "service": "shop_api",
        "content": "SYMPTOM x",
        "sha256": "0" * 64,
    }
    (d / "evidence_v5.json").write_text(
        json.dumps(
            {"incident_id": "i", "base_sha": "x", "compose_sha256": "0" * 64, "items": [item]}
        ),
        "utf-8",
    )
    (run / "records" / "shop_api-096.r0.json").write_text(
        json.dumps({"condition": condition, "pipeline_version": "v5"}), "utf-8"
    )
    return root, run


def loader(root, run, frozen=None):
    fn = make_real_run_fn(root / "datasets" / "manifests" / "dev.json", root / "runs" / "evidence",
                          root / "results" / "development" / "dev-axforge-L0-dd1-patch", "axforge",
                          "glm-5.3-flash", pipeline="v5", patch_from=run, frozen=frozen)  # fmt: skip
    return fn.load_saved


def test_saved_diagnosis_and_evidence_are_loaded_unchanged_after_the_frozen_check(tmp_path):
    root, run = make_saved_run(tmp_path)
    frozen = root / "frozen.json"
    frozen.write_text(json.dumps(fm.build([run], [], root)), "utf-8")
    sub, ev, source = loader(root, run, frozen)(N(case_id="shop_api-096"), "L0", 0)
    assert sub.qualname == "order_total" and ev.items[0].id == "EV-0001"
    assert source["run"] == "dev-axforge-L0-dd1-l1" and source["frozen_manifest"] == "frozen.json"
    (run / "cases" / "shop_api-096.r0" / "diagnosis.json").write_text(
        '{"cause_class": "configuration"}', "utf-8"
    )
    from traceforge.evaluation.real_run import MissingInputs

    with pytest.raises(MissingInputs, match="frozen diagnosis files not intact"):
        loader(root, run, frozen)(N(case_id="shop_api-096"), "L0", 0)


def test_saved_diagnosis_must_match_the_arm_and_must_not_be_an_abstention(tmp_path):
    from traceforge.evaluation.real_run import MissingInputs

    root, run = make_saved_run(tmp_path, condition="G0")
    with pytest.raises(MissingInputs, match="G0/v5"):
        loader(root, run)(N(case_id="shop_api-096"), "L0", 0)
    root2, run2 = make_saved_run(tmp_path / "b", abstained=True)
    with pytest.raises(MissingInputs, match="abstained"):
        loader(root2, run2)(N(case_id="shop_api-096"), "L0", 0)


# --- scoring -----------------------------------------------------------------------------------

CASE = {
    "case_id": "c1", "variant_group": "code:total_loop", "service": "shop_api", "cause_class": "application_code",
    "gold_config_keys": [], "gold_symbols": [{"path": "lab/shop_api/app/orders.py", "qualname": "order_total", "start_line": 10, "end_line": 15}],
}  # fmt: skip


def make_patch_run(
    tmp_path, *, diff=DIFF, hidden=True, vis_after=None, base=None, outcome="TEST_VERIFIED_IN_LAB"
):
    run, d = tmp_path / "run", tmp_path / "run" / "cases" / "c1.r0"
    d.mkdir(parents=True)
    (run / "records").mkdir()
    rec = {
        "condition": "L0", "outcome": outcome, "failure_reason": None, "tokens_in": 3000, "tokens_out": 120,
        "latency_ms": 4000, "cache_hits": 0,
        "diagnosis": {"cause_class": "application_code", "target": "lab/shop_api/app/orders.py::order_total"},
    }  # fmt: skip
    (run / "records" / "c1.r0.json").write_text(json.dumps(rec), "utf-8")
    (d / "attempt1.diff").write_text(diff, "utf-8")
    vis = vis_after or {"t::a": "passed", "t::b": "passed"}
    att = {"n": 1, "reasons": [], "visible_passed": all(v == "passed" for v in vis.values()), "has_diff": True,
           "counts": {"repro_passed": 2, "repro_failed": 0, "visible_passed": 2, "visible_failed": 0},
           "visible_outcomes": vis, "reproducer_outcomes": {}, "diff_stats": diff_stats(diff), "feedback_received": None}  # fmt: skip
    (d / "repair.json").write_text(
        json.dumps(
            {
                "attempts": [att],
                "hidden_passed": hidden,
                "hidden_counts": {"passed": 3 if hidden else 1, "failed": 0 if hidden else 2},
            }
        ),
        "utf-8",
    )
    (d / "baseline_visible.json").write_text(
        json.dumps(base or {"t::a": "failed", "t::b": "passed"}), "utf-8"
    )
    (d / "run_meta.json").write_text(
        json.dumps(
            {
                "tier": "development",
                "stage": "patch",
                "timings": {"model_s": 3.5},
                "patch_source": {"run": "x"},
            }
        ),
        "utf-8",
    )
    (d / "requests.jsonl").write_text(json.dumps({"stage": "patch"}) + "\n", "utf-8")
    ds = tmp_path / "datasets" / "cases" / "c1"
    ds.mkdir(parents=True)
    (ds / "mutation.patch").write_text(
        "--- a/lab/shop_api/app/orders.py\n+++ b/lab/shop_api/app/orders.py\n@@ -12,1 +12,1 @@\n-    for item in items:\n+    for item in items[:-1]:\n", "utf-8"
    )  # fmt: skip
    return run, tmp_path / "datasets"


def score(tmp_path, **kw):
    run, ds = make_patch_run(tmp_path, **kw)
    return patch_eval.score_case(run, CASE, ds)


def test_a_fixing_patch_is_scored_with_every_requested_metric(tmp_path):
    run, ds = make_patch_run(tmp_path)
    r = patch_eval.score_case(run, CASE, ds)
    assert (
        r["patch_generated"],
        r["patch_applied"],
        r["visible_passed"],
        r["hidden_passed"],
        r["fixed"],
    ) == (True, True, True, True, True)
    assert r["files"] == ["lab/shop_api/app/orders.py"] and (
        r["lines_added"],
        r["lines_removed"],
    ) == (1, 1)
    assert r["lines_within_gold_function"] is True and r["exact_gold_equivalent"] is True
    assert r["regressions_visible"] == [] and r["hidden_counts"] == {"passed": 3, "failed": 0}
    assert (r["tokens_in"], r["tokens_out"], r["latency_ms"], r["model_s"]) == (
        3000,
        120,
        4000,
        3.5,
    )
    assert (
        r["diagnose_requests"] == 0
        and r["stage"] == "patch"
        and r["touches_diagnosed_file"]
        and r["cache_hits"] == 0
    )


def test_a_test_that_passed_before_and_fails_after_is_a_regression(tmp_path):
    run, ds = make_patch_run(
        tmp_path, vis_after={"t::a": "passed", "t::b": "failed"}, hidden=False, outcome="REJECTED"
    )
    r = patch_eval.score_case(run, CASE, ds)
    assert (
        r["regressions_visible"] == ["t::b"]
        and r["fixed"] is False
        and r["visible_passed"] is False
    )
    assert r["hidden_passed"] is False and r["hidden_counts"] == {"passed": 1, "failed": 2}


def test_a_different_patch_is_not_reported_as_the_gold_fix_and_out_of_range_lines_are_flagged(
    tmp_path,
):
    other = DIFF.replace("items\n", "list(items)\n").replace(
        "-    for item in items[:-1]:\n+    for item in items:", "-    total = 0\n+    total = 0.0"
    )
    run, ds = make_patch_run(tmp_path, diff=other)
    r = patch_eval.score_case(run, CASE, ds)
    assert r["exact_gold_equivalent"] is False and r["lines_within_gold_function"] is True
    far = DIFF.replace("@@ -10,7 +10,7 @@", "@@ -90,7 +90,7 @@")
    r2 = score(tmp_path / "b", diff=far)
    assert r2["lines_within_gold_function"] is False


def test_summary_counts_by_arm_and_site(tmp_path):
    rows = [
        score(tmp_path / "a"),
        score(tmp_path / "b", hidden=False, outcome="REJECTED"),
    ]
    s = patch_eval.summarize(rows)["L0"]
    assert (s["cases"], s["patch_applied"], s["fixed"], s["hidden_passed"]) == (2, 2, 1, 1)
    assert s["sites"]["code:total_loop"] == {"cases": 2, "fixed": 1} and s["sites_with_a_fix"] == 1
