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


def test_conditions_default_to_the_official_provider_and_differ_only_in_the_studied_factors():
    for n in NAMES:
        c = load_condition(n)
        assert (c.provider, c.model_id) == ("axforge", "glm-5.3-flash")


def test_tier_is_official_only_for_axforge_glm_and_provider_override_is_recorded(
    manifest, tmp_path
):
    out = tmp_path / "runs"
    d = run_experiment(manifest, "L0", "off", fake(), out, **QUIET)
    meta = json.loads((d / "meta.json").read_text("utf-8"))
    assert meta["tier"] == "official" and meta["provider"] == "axforge"
    d2 = run_experiment(
        manifest, "L0", "dev", fake(), out, provider="beatapi", model="glm-5.3-flash-free", **QUIET
    )
    m2 = json.loads((d2 / "meta.json").read_text("utf-8"))
    assert (m2["tier"], m2["provider"], m2["model_id"]) == (
        "development",
        "beatapi",
        "glm-5.3-flash-free",
    )
    assert m2["condition_sha256"] != meta["condition_sha256"]  # different binding, different hash


def test_cases_that_are_not_ready_are_skipped_without_a_record_and_resume_later(manifest, tmp_path):
    out, calls, ready_ids = tmp_path / "runs", [], set()

    def ready(case):
        if case.case_id not in ready_ids:
            raise RuntimeError("no evidence bundle")

    run_fn = fake(calls)
    run_fn.ready = ready
    d = run_experiment(manifest, "L0", "r", run_fn, out, **QUIET)
    assert calls == [] and store.read_records(d) == []  # nothing recorded, nothing spent
    ready_ids.update({"case-0", "case-1"})
    run_experiment(manifest, "L0", "r", run_fn, out, **QUIET)
    assert calls == ["case-0", "case-1"]
    run_experiment(manifest, "L0", "r", run_fn, out, **QUIET)  # finished cases are never repeated
    assert calls == ["case-0", "case-1"]


def test_usage_report_keeps_providers_separate(tmp_path):
    from traceforge.evaluation import usage_report

    ax, bt = tmp_path / "ax.jsonl", tmp_path / "bt.jsonl"
    ax.write_text(
        json.dumps({"type": "request", "input_tokens": 100, "output_tokens": 20}) + chr(10),
        "utf-8",
    )
    bt.write_text(
        json.dumps({"input_tokens": 7, "output_tokens": 3, "usage_source": "provider"}) + chr(10),
        "utf-8",
    )
    r = usage_report.report(ax, bt)
    assert r["axforge"]["total_tokens"] == 120 and r["axforge"]["tier"] == "official"
    assert r["beatapi"]["total_tokens"] == 10 and r["beatapi"]["tier"] == "development"
    assert r["axforge"]["remaining_to_ceiling"] == 3_000_000 - 120


def test_parallel_workers_record_every_case_once_and_run_concurrently(manifest, tmp_path):
    import threading
    import time

    active, peak, lock, seen = 0, 0, threading.Lock(), []

    def slow(case, condition, rep):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            seen.append(case.case_id)
        time.sleep(0.3)
        with lock:
            active -= 1
        return AgentRunRecord.model_validate(
            {**REC, "case_id": case.case_id, "condition": condition}
        )

    t = time.time()
    d = run_experiment(
        manifest, "L0", "p", slow, tmp_path / "runs", split="dev", replicates=2, workers=4, **QUIET
    )
    wall = time.time() - t
    assert sorted(seen) == ["case-0", "case-0", "case-1", "case-1"]  # each task exactly once
    assert peak > 1 and wall < 1.0  # 4 tasks x 0.3 s ran concurrently, not one after another
    assert len(store.read_records(d)) == 4


def test_an_outage_in_parallel_mode_starts_no_new_case_and_records_no_result(manifest, tmp_path):
    import time

    calls = []

    def flaky(case, condition, rep):
        calls.append((case.case_id, rep))
        time.sleep(0.2)
        if case.case_id == "case-0" and rep == 0:
            raise StopRun("outage")
        return AgentRunRecord.model_validate(
            {**REC, "case_id": case.case_id, "condition": condition, "replicate": rep}
        )

    d = run_experiment(
        manifest, "L0", "o", flaky, tmp_path / "runs", split="dev", replicates=3, workers=2, **QUIET
    )
    recorded = {(r.case_id, r.replicate) for r in store.read_records(d)}
    assert ("case-0", 0) not in recorded  # an outage is not a result
    assert len(calls) < 6  # the rest of the queue was not started after the outage
    run_experiment(
        manifest, "L0", "o", fake(), tmp_path / "runs", split="dev", replicates=3, **QUIET
    )
    assert len(store.read_records(d)) == 6  # resume completes exactly the missing cases


def test_case_ids_select_exactly_those_and_unknown_ids_are_an_error(manifest, tmp_path):
    calls: list[str] = []
    run_experiment(
        manifest,
        "L0",
        "sel",
        fake(calls),
        tmp_path / "out",
        split="dev",
        case_ids=["case-1"],
        **QUIET,
    )
    assert calls == ["case-1"]
    with pytest.raises(ValueError, match="case-9"):
        run_experiment(
            manifest,
            "L0",
            "bad",
            fake([]),
            tmp_path / "out",
            split="dev",
            case_ids=["case-9"],
            **QUIET,
        )
