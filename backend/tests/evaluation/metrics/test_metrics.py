"""Metrics checked against hand-computed values (worked examples in each docstring)."""

import math

import pytest
from metric_builders import manifest, record

from traceforge.contracts.context import ContextBundle, ContextHit
from traceforge.evaluation.metrics import condition_section, section
from traceforge.evaluation.metrics.common import join, median, percentile
from traceforge.evaluation.metrics.diagnosis import diagnosis_metrics
from traceforge.evaluation.metrics.repair import repair_metrics
from traceforge.evaluation.metrics.retrieval import case_retrieval, retrieval_metrics
from traceforge.evaluation.metrics.system import system_metrics

KEY, SYM = "worker.REDIS_HOST", ("a.py", "f")


def fixture():
    """Four cases, one condition (L0).

    c1 config gold KEY            -> predicts configuration/KEY, verified, 1000 ms
    c2 code gold a.py::f          -> predicts configuration/a.py::f (wrong class, right target),
                                     REJECTED visible_failed, patch present, 2000 ms
    c3 runtime_dependency         -> predicts application_code/x.py::g, UNVERIFIED, 3000 ms
    c4 insufficient_evidence      -> abstains, 4000 ms
    """
    ms = [
        manifest("c1", "configuration", 1, keys=[KEY]),
        manifest("c2", "application_code", 0, syms=[SYM]),
        manifest("c3", "runtime_dependency"),
        manifest("c4", "insufficient_evidence"),
    ]
    rs = [
        record(
            "c1",
            target=KEY,
            outcome="TEST_VERIFIED_IN_LAB",
            patch_sha256="d" * 64,
            latency_ms=1000,
            attempts=1,
        ),
        record(
            "c2",
            cls="configuration",
            target="a.py::f",
            outcome="REJECTED",
            patch_sha256="e" * 64,
            latency_ms=2000,
            failure_reason="visible_failed",
            attempts=2,
        ),
        record(
            "c3",
            cls="application_code",
            target="x.py::g",
            outcome="UNVERIFIED",
            latency_ms=3000,
            failure_reason="sandbox_error",
        ),
        record("c4", cls="insufficient_evidence", latency_ms=4000),
    ]
    return join(rs, ms)


def test_diagnosis_hand_computed():
    """Accuracy: c1 yes, c2 no, c3 no, c4 yes = 2/4. Exact top-1: den = cases with gold target
    (c1, c2) = 2, both targets match = 2/2. Abstention (positive = should abstain): predicted
    abstain {c4}, gold abstain {c4} -> precision 1/1, recall 1/1. runtime_dependency: predicted
    none -> precision 0/0 (None), recall 0/1. Misdiagnosis: confident = c1,c2,c3; wrong c2,c3
    -> 2/3."""
    d = diagnosis_metrics(fixture())
    assert d["cause_class_accuracy"] == {"num": 2, "den": 4, "value": 0.5}
    assert (d["exact_target_top1"]["num"], d["exact_target_top1"]["den"]) == (2, 2)
    assert d["abstention"]["precision"] == {"num": 1, "den": 1, "value": 1.0}
    assert d["abstention"]["recall"]["den"] == 1
    assert d["runtime_dependency"]["precision"] == {"num": 0, "den": 0, "value": None}
    assert d["runtime_dependency"]["recall"] == {"num": 0, "den": 1, "value": 0.0}
    assert (d["misdiagnosis_rate"]["num"], d["misdiagnosis_rate"]["den"]) == (2, 3)


def test_repair_hand_computed():
    """Repairable (gold) = c1, c2 -> den 2. Verified 1/2. Patch present c1,c2 -> 2/2.
    Regressions (failure 'visible_failed') c2 -> 1/2. Unverified among repairable: 0/2
    (c3 is not repairable). Failure reasons over all 4 records."""
    r = repair_metrics(fixture())
    assert r["verified_repair_rate"] == {"num": 1, "den": 2, "value": 0.5}
    assert r["patch_apply_rate"]["num"] == 2
    assert r["regressions"] == {"count": 1, "den": 2}
    assert r["unverified"] == {"count": 0, "den": 2}
    assert r["failure_reasons"] == {
        "n_records": 4,
        "counts": {"sandbox_error": 1, "visible_failed": 1},
    }


def test_system_hand_computed():
    """Latencies [1000,2000,3000,4000]: median (2000+3000)/2 = 2500; P95 nearest-rank
    ceil(0.95*4)=4 -> 4000. list price 4 x 0.001 = 0.004; tool calls 8, invalid 0 -> 0/8."""
    s = system_metrics(fixture())
    assert s["latency_ms"]["median"] == 2500 and s["latency_ms"]["p95"] == 4000
    assert s["list_price_usd"]["total"] == pytest.approx(0.004)
    assert s["cost_usd"]["total"] == 0
    assert s["tokens_in"]["total"] == 40
    assert s["invalid_tool_call_rate"] == {"num": 0, "den": 8, "value": 0.0}


def test_percentile_and_median():
    """P95 of 1..20: ceil(19)=19th value = 19. Median of [5] = 5; of [] is None."""
    assert percentile([float(i) for i in range(1, 21)], 0.95) == 19
    assert median([5.0]) == 5 and median([]) is None and percentile([], 0.95) is None


def _bundle(node_ids, mode="G", used=100):
    hits = [
        ContextHit(
            node_id=n,
            kind="symbol",
            path="a.py",
            start_line=1,
            end_line=1,
            score=1.0,
            reasons=[],
            excerpt="x",
        )
        for n in node_ids
    ]
    return ContextBundle(incident_id="c", mode=mode, token_budget=1000, tokens_used=used, hits=hits)


def test_retrieval_hand_computed():
    """Gold = {cfg:K, sym:a.py::f}; ranked [x, sym:a.py::f, y, z, cfg:K].
    found@1=0, found@5=2 -> recall@1 0, recall@5 1.0. First relevant at rank 2 -> RR 0.5.
    DCG = 1/log2(3) + 1/log2(6) = 0.63093 + 0.38685 = 1.01778; ideal = 1 + 1/log2(3) = 1.63093;
    nDCG = 0.62404."""
    gold = {f"cfg:{KEY}", "sym:a.py::f"}
    r = case_retrieval(_bundle(["x", "sym:a.py::f", "y", "z", f"cfg:{KEY}"]), gold)
    assert (r["found@1"], r["found@5"], r["found@10"], r["rr"]) == (0, 2, 2, 0.5)
    assert r["ndcg@10"] == pytest.approx(0.62404, abs=1e-4)
    assert r["ndcg@10"] == pytest.approx(
        (1 / math.log2(3) + 1 / math.log2(6)) / (1 + 1 / math.log2(3))
    )


def test_retrieval_edge_cases():
    """No gold in the hits -> RR 0, nDCG 0 (not an error). Duplicate node ids count once, so
    [g, g] with gold {g, h} -> found 1 of 2. Perfect ranking -> nDCG 1. A case with no gold
    target is excluded: n=1 scored, n_without_gold=1."""
    assert case_retrieval(_bundle(["x", "y"]), {"g"})["rr"] == 0
    assert case_retrieval(_bundle(["x"]), {"g"})["ndcg@10"] == 0
    assert case_retrieval(_bundle(["g", "g"]), {"g", "h"})["found@5"] == 1
    assert case_retrieval(_bundle(["g", "h"]), {"g", "h"})["ndcg@10"] == pytest.approx(1.0)
    m_gold = manifest("c", "configuration", 1, keys=["K"])
    m_none = manifest("c", "runtime_dependency")
    out = retrieval_metrics([(_bundle(["cfg:K"]), m_gold), (_bundle(["cfg:K"]), m_none)])
    assert out["n"] == 1 and out["n_without_gold"] == 1
    assert out["recall@5"]["value"] == 1.0 and out["recall@5"]["pooled"]["den"] == 1
    assert retrieval_metrics([])["mrr"] == {"value": None, "n": 0}


def test_empty_and_all_abstain():
    """Empty group: counts 0, values None (never 0%). All abstain on a repairable case:
    accuracy 0/1, abstention precision 1/1 only if gold abstains else 0/1, misdiagnosis 0/0."""
    e = section([])
    assert e["diagnosis"]["cause_class_accuracy"] == {"num": 0, "den": 0, "value": None}
    assert e["system"]["latency_ms"]["median"] is None
    pairs = join(
        [record("c1", cls="insufficient_evidence")],
        [manifest("c1", "configuration", 1, keys=[KEY])],
    )
    d = diagnosis_metrics(pairs)
    assert d["cause_class_accuracy"]["num"] == 0
    assert d["abstention"]["precision"] == {"num": 0, "den": 1, "value": 0.0}
    assert d["misdiagnosis_rate"]["value"] is None
    assert d["exact_target_top1"] == {"num": 0, "den": 1, "value": 0.0}


def test_breakdowns_show_n_and_distance_buckets():
    """Distances 0,1,3 -> buckets '0','1','2+'; runtime_dependency has distance None -> 'none'."""
    ms = [manifest(f"c{i}", "configuration", d, keys=[KEY]) for i, d in enumerate([0, 1, 3])]
    ms.append(manifest("c9", "runtime_dependency"))
    rs = [record(m.case_id, target=KEY) for m in ms]
    cs = condition_section(join(rs, ms))
    assert set(cs["breakdowns"]["distance"]) == {"0", "1", "2+", "none"}
    assert cs["breakdowns"]["distance"]["2+"]["n_records"] == 1
    assert cs["overall"]["n_records"] == 4
    assert set(cs["breakdowns"]) == {"cause_class", "distance", "fault_family", "log_format"}


def test_join_rejects_unknown_and_duplicate():
    with pytest.raises(ValueError, match="unknown case"):
        join([record("zz")], [manifest("c1", keys=[KEY])])
    with pytest.raises(ValueError, match="duplicate"):
        join([record("c1"), record("c1", run_id="other")], [manifest("c1", keys=[KEY])])
