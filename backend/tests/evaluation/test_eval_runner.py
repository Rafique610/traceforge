import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from traceforge.contracts.agent_run import AgentRunRecord
from traceforge.evaluation import router as router_mod
from traceforge.evaluation import store
from traceforge.evaluation.conditions import ALIASES, NAMES, load_condition
from traceforge.evaluation.runner import FreezeError, StopRun, run_experiment

SAMPLES = Path(__file__).resolve().parents[2] / "traceforge/contracts/samples"
REC = json.loads((SAMPLES / "agent_run_record.code.json").read_text("utf-8"))
QUIET = {"log": lambda s: None}


@pytest.fixture
def manifest(tmp_path):
    cases = []
    for i, split in enumerate(["dev", "dev", "test"]):
        c = json.loads((SAMPLES / "case_manifest.code.json").read_text("utf-8"))
        c.update(case_id=f"case-{i}", split=split)
        cases.append(c)
    p = tmp_path / "data" / "manifest.json"
    p.parent.mkdir()
    p.write_text(json.dumps(cases), "utf-8")
    return p


def fake(calls=None, fail_on=None):
    def run_fn(case, condition, rep):
        if calls is not None:
            calls.append(case.case_id)
        if case.case_id == fail_on:
            raise StopRun("outage")
        return AgentRunRecord.model_validate(
            {**REC, "case_id": case.case_id, "condition": condition}
        )

    return run_fn


def test_conditions_load_and_equal_budgets():
    cs = [load_condition(n) for n in NAMES]
    assert [c.retrieval + str(int(c.feedback)) for c in cs] == list(NAMES)
    skip = {"name", "alias", "retrieval", "feedback"}
    shared = {json.dumps(c.model_dump(exclude=skip), sort_keys=True) for c in cs}
    assert len(shared) == 1 and cs[0].temperature == 0 and cs[0].max_attempts == 3
    assert {load_condition(a).name for a in ALIASES} == set(NAMES)
    with pytest.raises(ValueError):
        load_condition("X9")


def test_meta_records_and_listing(manifest, tmp_path):
    out = tmp_path / "runs"
    d = run_experiment(manifest, "G0F1", "r1", fake(), out, replicates=2, **QUIET)
    meta = json.loads((d / "meta.json").read_text("utf-8"))
    assert meta["condition"] == "L1" and meta["n_expected"] == 4 and meta["finished_at"]
    assert meta["dataset_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    for k in ("model_id", "provider", "temperature", "git_sha", "started_at", "env"):
        assert k in meta
    recs = store.read_records(d)
    assert len(recs) == 4 and {r.run_id for r in recs} == {"r1"}
    runs = store.list_runs(out)
    assert runs[0]["n_records"] == 4 and runs[0]["outcome_counts"] == {"UNVERIFIED": 4}
    assert runs[0]["complete"] and "records" not in runs[0]


def test_api(manifest, tmp_path, monkeypatch):
    run_experiment(manifest, "L0", "r1", fake(), tmp_path / "runs", **QUIET)
    monkeypatch.setenv("TRACEFORGE_RUNS_DIR", str(tmp_path / "runs"))
    app = FastAPI()
    app.include_router(router_mod.router)
    c = TestClient(app)
    assert c.get("/evaluation/runs").json()[0]["n_records"] == 2
    body = c.get("/evaluation/runs/r1").json()
    assert body["n_expected"] == 2 and len(body["records"]) == 2
    assert c.get("/evaluation/runs/nope").status_code == 404
    assert c.get("/evaluation/runs/.hidden").status_code == 422


def test_resume_after_interrupt(manifest, tmp_path):
    out, calls = tmp_path / "runs", []
    d = run_experiment(manifest, "L0", "r1", fake(calls, fail_on="case-1"), out, **QUIET)
    assert len(store.read_records(d)) == 1
    assert json.loads((d / "meta.json").read_text("utf-8"))["finished_at"] is None
    calls.clear()
    run_experiment(manifest, "L0", "r1", fake(calls), out, **QUIET)
    assert calls == ["case-1"] and len(store.read_records(d)) == 2
    with pytest.raises(ValueError):
        run_experiment(manifest, "G0", "r1", fake(), out, **QUIET)


def test_crash_recorded_and_run_continues(manifest, tmp_path):
    def boom(case, cond, rep):
        raise KeyError("x")

    d = run_experiment(manifest, "L0", "r1", boom, tmp_path / "runs", **QUIET)
    recs = store.read_records(d)
    assert len(recs) == 2 and "pipeline_crash" in recs[0].failure_reason


def test_freeze_guard(manifest, tmp_path):
    out = tmp_path / "runs"
    with pytest.raises(FreezeError):
        run_experiment(manifest, "L0", "t", fake(), out, split="test")
    (manifest.parent / "test.sha256").write_text("0" * 64, "utf-8")
    with pytest.raises(FreezeError):
        run_experiment(manifest, "L0", "t", fake(), out, split="test")
    sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    (manifest.parent / "test.sha256").write_text(sha + "  manifest.json\n", "utf-8")
    d = run_experiment(manifest, "L0", "t", fake(), out, split="test", **QUIET)
    assert [r.case_id for r in store.read_records(d)] == ["case-2"]


def test_records_endpoint(manifest, tmp_path, monkeypatch):
    run_experiment(manifest, "L0", "r1", fake(), tmp_path / "runs", replicates=2, **QUIET)
    monkeypatch.setenv("TRACEFORGE_RUNS_DIR", str(tmp_path / "runs"))
    app = FastAPI()
    app.include_router(router_mod.router)
    c = TestClient(app)
    p = c.get("/evaluation/runs/r1/records?limit=3&offset=1").json()
    assert p["total"] == 4 and p["limit"] == 3 and len(p["items"]) == 3
    assert p["items"][0]["case_id"] == "case-0"
    assert {
        "outcome",
        "attempts",
        "hidden_passed",
        "failure_reason",
        "tokens_in",
        "tokens_out",
        "latency_ms",
    } <= set(p["items"][0])
    assert "failure_reason_counts" in c.get("/evaluation/runs/r1").json()
    assert c.get("/evaluation/runs/nope/records").status_code == 404
    assert c.get("/evaluation/runs/r1/records?limit=0").status_code == 422
    assert c.get("/evaluation/runs/r1/records?offset=-1").status_code == 422
    assert c.get("/evaluation/runs/..bad%20id/records").status_code == 422
