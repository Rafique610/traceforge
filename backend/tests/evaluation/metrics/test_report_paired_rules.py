"""Paired comparison, dataset guard, report/CLI/router and the rule baseline."""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from metric_builders import SHA, manifest, record

from traceforge.contracts.evidence import EvidenceBundle
from traceforge.evaluation.analysis import report as rep
from traceforge.evaluation.baselines.rules import baseline_records, diagnose_by_rules
from traceforge.evaluation.metrics.common import join
from traceforge.evaluation.metrics.paired import bootstrap_ci, paired_comparison

SAMPLES = Path(__file__).parents[3] / "traceforge" / "contracts" / "samples"
KEY = "worker.REDIS_HOST"


def _cases(n):
    return [manifest(f"c{i}", "configuration", 1, keys=[KEY]) for i in range(n)]


def test_paired_hand_computed_and_replicate_mean():
    """10 cases. A fails everywhere except c0, where its two replicates are 1 and 0 (mean 0.5).
    B verifies c0..c3. Per-case diffs b-a: c0 1-0.5=+0.5, c1..c3 +1, rest 0 -> mean 3.5/10=0.35;
    mean_a 0.05, mean_b 0.4; better 4, worse 0, tied 6."""
    ms = _cases(10)
    rs = [
        record("c0", "L0", target=KEY, outcome="TEST_VERIFIED_IN_LAB", replicate=0),
        record("c0", "L0", target=KEY, outcome="REJECTED", replicate=1),
    ]
    rs += [record(f"c{i}", "L0", target=KEY, outcome="REJECTED") for i in range(1, 10)]
    rs += [record(f"c{i}", "G0", target=KEY, outcome="TEST_VERIFIED_IN_LAB") for i in range(4)]
    rs += [record(f"c{i}", "G0", target=KEY, outcome="REJECTED") for i in range(4, 10)]
    p = paired_comparison(join(rs, ms), "L0", "G0", "verified_repair", iterations=500, seed=1)
    assert p["n_paired"] == 10
    assert p["mean_a"] == pytest.approx(0.05) and p["mean_b"] == pytest.approx(0.4)
    assert p["mean_diff"] == pytest.approx(0.35)
    assert (p["b_better"], p["b_worse"], p["tied"]) == (4, 0, 6)
    lo, hi = p["ci95"]
    assert lo <= 0.35 <= hi
    assert p == paired_comparison(join(rs, ms), "L0", "G0", "verified_repair", 500, 1)


def test_paired_only_shared_cases_and_small_n_has_no_ci():
    """c0 in both, c1 only in A: n_paired 1, n_only_a 1, no CI below 10 cases."""
    ms = _cases(2)
    rs = [
        record("c0", "L0", target=KEY),
        record("c1", "L0", target=KEY),
        record("c0", "G0", target=KEY),
    ]
    p = paired_comparison(join(rs, ms), "L0", "G0", "cause_correct")
    assert (p["n_paired"], p["n_only_a"], p["n_only_b"]) == (1, 1, 0)
    assert p["ci95"] is None and "no CI" in p["ci_note"]
    assert bootstrap_ci([1.0] * 3) is None


def test_bootstrap_constant_diffs():
    """Ten diffs all 0.5: every resample mean is 0.5, so the CI is exactly (0.5, 0.5)."""
    assert bootstrap_ci([0.5] * 10, iterations=200) == (0.5, 0.5)


def test_dataset_hash_guard():
    ms = _cases(1)
    r = record("c0", target=KEY)
    rep.report([r], ms, manifest_sha256=SHA)  # matches
    with pytest.raises(rep.DatasetMismatch):
        rep.report([r], ms, manifest_sha256="f" * 64)
    other = record("c0", "G0", target=KEY, dataset_sha256="9" * 64)
    with pytest.raises(rep.DatasetMismatch):
        rep.report([r, other], ms)  # no manifest hash: records must agree with each other


def test_report_shape_and_empty():
    out = rep.report(
        [record("c0", target=KEY)], _cases(1), manifest_sha256=SHA, bootstrap_iterations=10
    )
    assert out["dataset"]["verified_against_manifest"] is True
    assert out["conditions"]["L0"]["overall"]["diagnosis"]["cause_class_accuracy"]["den"] == 1
    json.dumps(out)
    empty = rep.report([], _cases(1))
    assert (
        empty["n_records"] == 0 and empty["conditions"] == {} and empty["dataset"]["sha256"] is None
    )


def _write_run(runs: Path, rid: str, recs) -> None:
    (runs / rid / "records").mkdir(parents=True)
    (runs / rid / "meta.json").write_text("{}")
    for r in recs:
        (runs / rid / "records" / f"{r.case_id}.r0.json").write_text(r.model_dump_json())


def test_cli_and_router(tmp_path, monkeypatch, capsys):
    ms = _cases(1)
    mpath = tmp_path / "m.json"
    mpath.write_text(json.dumps([m.model_dump() for m in ms]))
    import hashlib

    sha = hashlib.sha256(mpath.read_bytes()).hexdigest()
    runs = tmp_path / "runs"
    _write_run(runs, "good", [record("c0", target=KEY, dataset_sha256=sha)])
    _write_run(runs, "stale", [record("c0", "G0", target=KEY)])  # SHA != manifest hash
    assert rep.main(["--runs-dir", str(runs), "--manifest", str(mpath), "--run-id", "good"]) == 0
    assert json.loads(capsys.readouterr().out)["dataset"]["sha256"] == sha
    assert rep.main(["--runs-dir", str(runs), "--manifest", str(mpath), "--run-id", "stale"]) == 2

    from traceforge.evaluation.analysis.router import router

    app = FastAPI()
    app.include_router(router)
    monkeypatch.setenv("TRACEFORGE_RUNS_DIR", str(runs))
    monkeypatch.setenv("TRACEFORGE_MANIFEST", str(mpath))
    c = TestClient(app)
    assert c.get("/evaluation/report", params={"run_ids": "good"}).status_code == 200
    assert c.get("/evaluation/report", params={"run_ids": "stale"}).status_code == 409
    assert c.get("/evaluation/report", params={"run_ids": "nope"}).status_code == 404
    assert c.get("/evaluation/report", params={"run_ids": "../x"}).status_code == 422


def _bundle(name):
    return EvidenceBundle.model_validate_json(
        (SAMPLES / f"evidence_bundle.{name}.json").read_text()
    )


def test_rules_on_contract_samples():
    """Sample evidence: config -> worker.REDIS_HOST ('redsi' bound by REDIS_HOST, not a healthy
    service); code -> innermost frame orders.py::order_total; abstain -> abstains."""
    d = diagnose_by_rules(_bundle("config"))
    assert (d.cause_class, d.target) == ("configuration", KEY)
    d = diagnose_by_rules(_bundle("code"))
    assert (d.cause_class, d.target) == (
        "application_code",
        "lab/shop_api/app/orders.py::order_total",
    )
    d = diagnose_by_rules(_bundle("abstain"))
    assert d.abstained and d.target is None


def test_rules_runtime_dependency_when_container_unhealthy():
    b = _bundle("config")
    items = [
        i.model_copy(update={"content": "container traceforge-lab-redis-1: exited (1)"})
        if i.id == "EV-0005"
        else i
        for i in b.items
    ]
    d = diagnose_by_rules(b.model_copy(update={"items": items}))
    # host in the error is 'redsi' (not redis) -> still configuration; now point the error at redis
    assert d.cause_class == "configuration"
    items = [i.model_copy(update={"content": i.content.replace("redsi", "redis")}) for i in items]
    d = diagnose_by_rules(b.model_copy(update={"items": items}))
    assert d.cause_class == "runtime_dependency" and d.target is None


def test_baseline_records_scored_by_same_metrics():
    """RULES records flow through report(); on the 3 samples the rules are right on the config
    and code cases (2/3 class accuracy would need the abstain case right too: it is) -> 3/3."""
    ms = [
        manifest("cfg", "configuration", 1, keys=[KEY]),
        manifest(
            "code", "application_code", 0, syms=[("lab/shop_api/app/orders.py", "order_total")]
        ),
        manifest("abs", "insufficient_evidence"),
    ]
    bundles = {"cfg": _bundle("config"), "code": _bundle("code"), "abs": _bundle("abstain")}
    recs = baseline_records(bundles, ms, SHA)
    out = rep.report(recs, ms, manifest_sha256=SHA, bootstrap_iterations=10)
    d = out["conditions"]["RULES"]["overall"]["diagnosis"]
    assert d["cause_class_accuracy"] == {"num": 3, "den": 3, "value": 1.0}
    assert d["exact_target_top1"]["num"] == 2
    with pytest.raises(ValueError, match="no evidence bundle"):
        baseline_records({}, ms, SHA)
