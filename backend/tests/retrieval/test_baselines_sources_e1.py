"""R0, trace-only, RealContextSource and the E1 harness (hand-written test evidence)."""

import json
from pathlib import Path

from retr_helpers import bundle, item

from traceforge.codeintel import build_graph
from traceforge.contracts.case_manifest import CaseManifest, GoldSymbol
from traceforge.retrieval import RealContextSource
from traceforge.retrieval.baselines import r0_impl, run_baseline
from traceforge.retrieval.e1 import format_table, run_e1


def test_r0_ranks_by_matching_line_count(tiny_repo):
    g = build_graph(tiny_repo, "t", cache_dir=None)
    ev = bundle(
        item(1, "log", "ERROR parse_quantity failed for raw input"),
        item(2, "trace_frame", "f", path="app/inventory.py", line=5),
    )
    b = run_baseline("R0", ev, g, 2000)
    ids = [h.node_id for h in b.hits]
    assert r0_impl() in ("ripgrep", "python-fixed-string")
    # reserve_stock mentions the term on 2 of its own lines, parse_quantity on 1
    assert (
        ids[0] == "sym:app/orders.py::parse_quantity"
        or ids[0] == "sym:app/inventory.py::reserve_stock"
    )
    assert b.hits[0].reasons[0].endswith("matching lines")
    assert run_baseline("R0", ev, g, 2000) == b


def test_trace_only_is_just_the_project_frames_innermost_first(lab_graph, crash_evidence):
    b = run_baseline("trace_only", crash_evidence, lab_graph, 3000)
    assert [h.node_id for h in b.hits] == [
        "sym:lab/worker/queue.py::make_client",
        "sym:lab/worker/main.py::main",
    ]
    assert b.mode == "L" and b.tokens_used <= b.token_budget


def test_real_context_source(lab_tree, lab_graph, crash_evidence):
    src = RealContextSource(lab_tree, lab_graph)
    case = CaseManifest.model_validate_json(
        (
            Path(__file__).resolve().parents[2]
            / "traceforge/contracts/samples/case_manifest.config.json"
        ).read_text("utf-8")
    )
    text = src.read_symbol(case, "lab/worker/queue.py", "make_client")
    assert text and text.startswith("19: def make_client")
    assert src.read_symbol(case, "lab/worker/settings.py", "WorkerSettings.redis_host")
    assert src.read_symbol(case, "lab/worker/queue.py", "nope") is None
    assert src.read_symbol(case, "../etc/passwd", "x") is None
    assert src.read_symbol(case, "datasets/hidden_tests/x.py", "x") is None
    near = src.neighbors("sym:lab/worker/queue.py::make_client")
    assert "cfg:REDIS_HOST" in near  # neighbours use the bare graph key (no service context)
    assert src.neighbors("sym:nope.py::x") == []
    assert "lab/worker/queue.py" in src.code_map()
    for mode in "LG":
        b = src.retrieve(crash_evidence, lab_graph, mode, 2000)
        assert b.mode == mode and b.tokens_used <= 2000


_FIELD = "WorkerSettings.redis_host"


def _manifest_case() -> CaseManifest:
    return CaseManifest(
        case_id="t-cfg-1", split="dev", cause_class="configuration", fault_family="wrong_host",
        service="worker", base_sha="x", gold_config_keys=["worker.REDIS_HOST"],
        gold_symbols=[GoldSymbol(path="lab/worker/settings.py", qualname=_FIELD,
                                 start_line=11, end_line=11)],
        distance=1, reproducer_id="r", hidden_test_ids=["h::t"], variant_group="v",
    )  # fmt: skip


def test_e1_harness_end_to_end(lab_tree, crash_evidence, tmp_path):
    manifest = tmp_path / "dev.json"
    manifest.write_text(json.dumps([_manifest_case().model_dump(mode="json")]))
    ev_dir = tmp_path / "ev"
    ev_dir.mkdir()
    (ev_dir / "t-cfg-1.json").write_text(crash_evidence.model_dump_json())
    res = run_e1(manifest, lab_tree, ev_dir, tmp_path / "runs", 3000, "e1-test")
    assert res["n_scored"] == 1 and res["skipped"] == []
    assert res["dataset_sha256"] and set(res["methods"]) == {"R0", "trace_only", "L", "G"}
    for m in res["methods"].values():
        assert m["overall"]["n"] == 1 and "0" not in m["by_distance"]
        assert m["by_distance"]["1"]["n"] == 1 and m["by_fault_family"]["wrong_host"]["n"] == 1
    for r in res["cases"]:
        assert r["tokens_used"] <= 3000
    g = next(r for r in res["cases"] if r["method"] == "G")
    assert g["first_gold_rank"] is not None
    out = tmp_path / "runs" / "e1-test"
    assert (out / "result.json").is_file() and (out / "bundles" / "G" / "t-cfg-1.json").is_file()
    assert "G" in format_table(res)


def test_e1_skips_cases_without_saved_evidence(lab_tree, tmp_path):
    manifest = tmp_path / "dev.json"
    manifest.write_text(json.dumps([_manifest_case().model_dump(mode="json")]))
    res = run_e1(manifest, lab_tree, None, tmp_path / "runs", 3000, "e1-none")
    assert res["n_scored"] == 0 and res["skipped"][0]["reason"] == "no saved EvidenceBundle"
