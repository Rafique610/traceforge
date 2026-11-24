# ruff: noqa: E501
"""The offline diagnosis scorer (evaluation only): metrics, validity indicators, real artifacts."""

import json
from pathlib import Path

import pytest

from traceforge.evaluation.diag_eval import score_case, summarize

GOLD = "lab/shop_api/app/orders.py::order_total"
CASE = {
    "case_id": "c1", "variant_group": "code:total_loop", "service": "shop_api",
    "cause_class": "application_code", "gold_config_keys": [],
    "gold_symbols": [{"path": "lab/shop_api/app/orders.py", "qualname": "order_total"}],
}  # fmt: skip


def make_run(tmp_path, *, target=GOLD, cited=("EV-0002",), symptom_text="test_order_total_endpoint",
             rationale="order_total loops over items[:-1] so the last line is skipped",
             abstained=False, sent=(GOLD,), reads=1, retrieval=True):  # fmt: skip
    run, d = tmp_path / "run", tmp_path / "run" / "cases" / "c1.r0"
    d.mkdir(parents=True)
    (run / "records").mkdir()
    cls = "insufficient_evidence" if abstained else "application_code"
    rec = {
        "condition": "L0", "failure_reason": "diagnosis_only", "tool_calls": 2, "invalid_tool_calls": 1,
        "tokens_in": 1000, "tokens_out": 100, "latency_ms": 5, "cache_hits": 0,
        "diagnosis": {"cause_class": cls, "target": None if abstained else target,
                      "abstained": abstained, "evidence_ids": [], "contradicting_ids": []},
    }  # fmt: skip
    (run / "records" / "c1.r0.json").write_text(json.dumps(rec), "utf-8")
    (d / "run_meta.json").write_text(json.dumps({"tier": "development", "diagnosis_rejected_calls": 1,
        "symptom_status": "ok", "timings": {"model_s": 12.5}}), "utf-8")  # fmt: skip
    (d / "diagnosis.json").write_text(json.dumps({"supporting_evidence_ids": list(cited),
        "rationale": rationale, "observed_symptom": "total is short"}), "utf-8")  # fmt: skip
    (d / "trace.json").write_text(json.dumps([{"tool": "read_symbol", "ok": bool(reads)},
                                              {"tool": "submit_diagnosis", "ok": True}]), "utf-8")  # fmt: skip
    (d / "symptom.json").write_text(json.dumps({"items": [{"test_id": symptom_text}]}), "utf-8")
    (d / "evidence_v5.json").write_text(json.dumps({"items": [
        {"id": "EV-0001", "content": "health ok"}, {"id": "EV-0002", "content": "SYMPTOM failing test"}]}), "utf-8")  # fmt: skip
    (d / "context_sent.json").write_text(json.dumps({"n_rendered": len(sent), "n_retrieved": 5,
        "hits": [{"path": s.split("::")[0], "id": "sym:" + s} for s in sent]}), "utf-8")  # fmt: skip
    (d / "requests.jsonl").write_text(json.dumps({"stage": "diagnose"}) + "\n", "utf-8")
    if retrieval:
        row = lambda i, p, rel: {"id": f"sym:{p}::{i}", "path": p, "relevant_to_symptom": rel}  # noqa: E731
        (d / "retrieval.json").write_text(json.dumps({
            "L": [row("a", "lab/x.py", True), row("order_total", "lab/shop_api/app/orders.py", True)],
            "G": [row("order_total", "lab/shop_api/app/orders.py", True), row("z", "lab/y.py", False)],
            "overlap": 1, "only_L": ["sym:lab/x.py::a"], "only_G": ["sym:lab/y.py::z"],
            "relevant": {"L": 2, "G": 1}, "only_G_relevant": 0, "only_L_relevant": 1}), "utf-8")  # fmt: skip
    ds = tmp_path / "datasets" / "cases" / "c1"
    ds.mkdir(parents=True)
    (ds / "mutation.patch").write_text(
        "--- a\n+++ b\n-    for item in items:\n+    for item in items[:-1]:\n", "utf-8"
    )
    return run, tmp_path / "datasets"


def test_correct_supported_diagnosis_is_scored_with_all_metrics(tmp_path):
    run, ds = make_run(tmp_path)
    r = score_case(run, CASE, ds)
    assert (r["correct_class"], r["correct_file"], r["exact_function"]) == (True, True, True)
    assert r["cited_all_exist"] and r["cites_symptom"] and r["unsupported_claims"] == []
    assert r["target_in_context_sent"] and r["gold_in_context_sent"]
    assert (r["tool_calls"], r["invalid_calls"], r["rejected_calls"], r["model_s"]) == (
        2,
        1,
        1,
        12.5,
    )
    assert r["tier"] == "development" and r["cache_hits"] == 0 and r["requests"] == 1


def test_retrieval_record_gives_ranks_overlap_and_unique_irrelevant_hits(tmp_path):
    run, ds = make_run(tmp_path)
    ret = score_case(run, CASE, ds)["retrieval"]
    assert (ret["gold_rank_L"], ret["gold_rank_G"]) == (2, 1)
    assert (ret["overlap"], ret["only_L"], ret["only_G"]) == (1, 1, 1)
    assert ret["only_G_irrelevant"] == ["sym:lab/y.py::z"] and ret["only_L_irrelevant"] == []


def test_identifier_exposure_and_source_reasoning_are_separate_indicators(tmp_path):
    run, ds = make_run(tmp_path)
    r = score_case(run, CASE, ds)
    assert r["identifier_exposed"] == ["order_total"]  # the visible test name carries the gold name
    assert any("items[:-1]" in q for q in r["source_reasoned_quotes"])  # quotes the faulty line
    run2, ds2 = make_run(tmp_path / "b", symptom_text="test_totals", rationale="the total is wrong")
    r2 = score_case(run2, CASE, ds2)
    assert r2["identifier_exposed"] == [] and r2["source_reasoned_quotes"] == []


def test_wrong_target_unseen_target_and_unknown_citation_are_flagged(tmp_path):
    run, ds = make_run(tmp_path, target="lab/shop_api/app/settings.py::Settings.db_host",
                       cited=("EV-0002", "EV-9999"), sent=(GOLD,), reads=0)  # fmt: skip
    r = score_case(run, CASE, ds)
    assert not r["exact_function"] and not r["correct_file"]
    assert "EV-9999" in r["unsupported_claims"] and "target_never_seen" in r["unsupported_claims"]
    assert r["cited_all_exist"] is False


def test_abstention_and_summary_by_site_and_arm(tmp_path):
    run, ds = make_run(tmp_path, abstained=True)
    r = score_case(run, CASE, ds)
    assert r["abstained"] and not r["exact_function"] and not r["correct_class"]
    run_ok, ds_ok = make_run(tmp_path / "ok")
    rows = [score_case(run_ok, CASE, ds_ok), r | {"case": "c2"}]
    s = summarize(rows)["L0"]
    assert (s["cases"], s["exact_function"], s["abstained"]) == (2, 1, 1)
    assert s["sites"]["code:total_loop"] == {"cases": 2, "exact_function": 1}
    assert s["sites_with_at_least_one_exact"] == 1


def test_a_missing_case_returns_none(tmp_path):
    run, ds = make_run(tmp_path)
    assert score_case(run, {**CASE, "case_id": "nope"}, ds) is None


REAL = Path(__file__).resolve().parents[3] / "results/development/dev-axforge-L0-dd1-l1"


@pytest.mark.skipif(not (REAL / "records/shop_api-014.r0.json").exists(), reason="no saved run")
def test_saved_014_artifacts_score_as_a_correct_supported_diagnosis():
    manifest = REAL.parents[2] / "datasets/manifests/dev.json"
    case = next(
        c for c in json.loads(manifest.read_text("utf-8")) if c["case_id"] == "shop_api-014"
    )
    r = score_case(REAL, case, manifest.parents[1])
    assert r["exact_function"] and r["cites_symptom"] and r["cited_all_exist"]
    assert r["tier"] == "development" and r["cache_hits"] == 0 and r["gold_in_context_sent"]
    assert r["identifier_exposed"] == ["reserve"] and r["retrieval"]["gold_rank_L"] is not None


def test_a_config_key_target_is_not_flagged_as_never_seen(tmp_path):
    run, ds = make_run(tmp_path, target="shop_api.REDIS_HOST", reads=0, sent=(GOLD,))
    r = score_case(
        run,
        {
            **CASE,
            "cause_class": "configuration",
            "gold_symbols": [],
            "gold_config_keys": ["REDIS_HOST"],
        },
        ds,
    )
    assert r["unsupported_claims"] == [] and r["exact_function"]  # a key is not a code symbol
