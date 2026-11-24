"""Job scheduler for two key slots: fake command runner only; nothing is executed or sent."""

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from traceforge.evaluation import scheduler as sch
from traceforge.evaluation.scheduler import Job, Scheduler, SchedulerBusy

ROOT = Path(__file__).resolve().parents[3]


class Fake:
    """Fake command runner: records (job tag, slot) calls, tracks concurrency, can fail by tag."""

    def __init__(self, fail=(), hold=0.0, on_run=None):
        self.calls, self.fail, self.hold, self.on_run = [], set(fail), hold, on_run
        self.lock, self.now, self.max_per, self.max_all = threading.Lock(), {}, {}, 0

    def __call__(self, args, slot):
        tag = args[0]
        with self.lock:
            self.calls.append((tag, slot))
            self.now[slot] = self.now.get(slot, 0) + 1
            self.max_per[slot] = max(self.max_per.get(slot, 0), self.now[slot])
            self.max_all = max(self.max_all, sum(self.now.values()))
        try:
            time.sleep(self.hold)
            if self.on_run:
                self.on_run(tag, slot)
            return 1 if tag in self.fail else 0
        finally:
            with self.lock:
                self.now[slot] -= 1

    def tags(self):
        return [t for t, _ in self.calls]


def make(tmp_path, jobs, fake, **kw):
    kw.setdefault("poll_s", 0.02)
    kw.setdefault("pacing_file", lambda s: tmp_path / f"pace{s}.json")
    return Scheduler(
        jobs, tmp_path / "state.json", fake, base_dir=tmp_path, log=lambda m: None, **kw
    )


def J(i, deps=(), slot="auto", **kw):
    return Job(id=i, args=[i], deps=list(deps), slot=slot, **kw)


def state(tmp_path):
    return json.loads((tmp_path / "state.json").read_text("utf-8"))


def test_one_job_per_slot_two_slots_concurrently(tmp_path):
    f = Fake(hold=0.1)
    res = make(tmp_path, [J("a"), J("b"), J("c"), J("d")], f).run()
    assert sorted(f.tags()) == ["a", "b", "c", "d"] and len(res["jobs"]["done"]) == 4
    assert f.max_per == {"1": 1, "2": 1}  # never two jobs on one key
    assert f.max_all == 2  # both keys busy at once


def test_dependency_order_and_pinned_slots(tmp_path):
    f = Fake(hold=0.05)
    jobs = [J("l1", deps=["l0"], slot="1"), J("l0", slot="2"), J("g0")]
    make(tmp_path, jobs, f).run()
    assert f.tags().index("l0") < f.tags().index("l1")
    assert ("l0", "2") in f.calls and ("l1", "1") in f.calls


def test_validation_rejects_cycles_unknown_deps_and_key_args():
    with pytest.raises(ValueError, match="cycle"):
        sch.validate([J("a", ["b"]), J("b", ["a"])])
    with pytest.raises(ValueError, match="unknown"):
        sch.validate([J("a", ["zz"])])
    with pytest.raises(ValueError, match="duplicate"):
        sch.validate([J("a"), J("a")])
    with pytest.raises(ValueError, match="axforge-key"):
        sch.validate([Job(id="a", args=["--axforge-key", "2"])])


def test_existing_records_are_not_rerun_and_unblock_dependents(tmp_path):
    rec = tmp_path / "runs" / "l0" / "records"
    rec.mkdir(parents=True)
    (rec / "c1.json").write_text("{}", "utf-8")
    f = Fake()
    jobs = [J("l0", done_glob="runs/l0/records/*.json"), J("l1", ["l0"])]
    res = make(tmp_path, jobs, f).run()
    assert f.tags() == ["l1"]  # l0 skipped, dependents proceed
    assert state(tmp_path)["jobs"]["l0"]["skipped"] is True and res["jobs"]["done"] == ["l0", "l1"]
    # a callable check and min_records
    f2 = Fake()
    make(
        tmp_path, [J("x", done_check=lambda: True), J("y", done_glob="nope/*", min_records=1)], f2
    ).run()
    assert f2.tags() == ["y"]


def test_failed_job_halts_its_slot_is_not_retried_and_pending_auto_fails_over(tmp_path):
    f = Fake(fail={"a"}, hold=0.05)
    jobs = [J("a", slot="1"), J("b"), J("c"), J("pinned1", slot="1"), J("d", deps=["a"])]
    res = make(tmp_path, jobs, f).run()
    assert f.tags().count("a") == 1  # never retried automatically
    assert ("b", "1") not in f.calls and ("c", "1") not in f.calls
    assert ("b", "2") in f.calls and ("c", "2") in f.calls  # failover to the healthy slot
    assert "pinned1" not in f.tags() and "d" not in f.tags()  # pinned/blocked stay pending
    assert res["jobs"]["failed"] == ["a"] and set(res["jobs"]["pending"]) == {"pinned1", "d"}
    assert "1" in res["halted_slots"]
    st = state(tmp_path)
    assert st["jobs"]["a"]["exit_code"] == 1 and st["slots"]["1"]["halted"]


def test_a_crashing_runner_is_a_failure(tmp_path):
    def boom(args, slot):
        raise OSError("secret-ish detail")

    res = make(tmp_path, [J("a", slot="1")], boom).run()
    assert res["jobs"]["failed"] == ["a"] and state(tmp_path)["jobs"]["a"]["exit_code"] == -1


def test_state_is_persisted_each_change_and_a_restart_resumes_without_duplicates(tmp_path):
    seen = []

    def peek(tag, slot):  # state on disk while the job is running
        seen.append(state(tmp_path)["jobs"][tag]["status"])

    f = Fake(fail={"b"}, on_run=peek)
    jobs = [J("a", slot="1"), J("b", ["a"], slot="1"), J("c", ["b"], slot="1")]
    make(tmp_path, jobs, f).run()
    assert seen[0] == "running" and f.tags() == ["a", "b"]
    # restart: a stays done, b stays failed (no automatic retry), c still blocked
    f2 = Fake()
    res = make(tmp_path, jobs, f2).run()
    assert f2.tags() == [] and res["jobs"]["failed"] == ["b"]
    # deliberate manual resume
    f3 = Fake()
    res = make(tmp_path, jobs, f3, retry_failed=True).run()
    assert f3.tags() == ["b", "c"] and len(res["jobs"]["done"]) == 3


def test_a_job_left_running_by_a_killed_scheduler_goes_back_to_pending(tmp_path):
    (tmp_path / "state.json").write_text(
        json.dumps({"jobs": {"a": {"status": "running", "slot": "1"}}}), "utf-8"
    )
    f = Fake()
    make(tmp_path, [J("a")], f).run()
    assert f.tags() == ["a"] and state(tmp_path)["jobs"]["a"]["interrupted"] is True


def test_only_one_scheduler_at_a_time(tmp_path):
    started, release = threading.Event(), threading.Event()

    def slow(tag, slot):
        started.set()
        release.wait(5)

    t = threading.Thread(target=make(tmp_path, [J("a")], Fake(on_run=slow)).run)
    t.start()
    assert started.wait(5)
    with pytest.raises(SchedulerBusy):
        make(tmp_path, [J("b")], Fake()).run()
    release.set()
    t.join()
    make(tmp_path, [J("b")], Fake()).run()  # lock released afterwards


def test_retry_after_cools_only_that_slot_and_auto_jobs_use_the_other(tmp_path):
    clock = [1000.0]
    (tmp_path / "pace1.json").write_text(json.dumps({"blocked_until": 1500.0}), "utf-8")
    f = Fake()
    jobs = [J("a"), J("b"), J("pin1", slot="1")]
    s = make(tmp_path, jobs, f, now=lambda: clock[0])
    # slot 1 blocked until 1500: a, b go to slot 2; pin1 waits; advance the clock to release it
    t = threading.Thread(target=s.run)
    t.start()
    time.sleep(0.3)
    assert ("a", "2") in f.calls and ("b", "2") in f.calls and "pin1" not in f.tags()
    assert "1" not in s.halted  # cooling, not halted
    clock[0] = 1600.0
    t.join(5)
    assert ("pin1", "1") in f.calls and not t.is_alive()


def test_dry_run_plans_without_running(tmp_path, capsys):
    sys.path.insert(0, str(ROOT / "scripts"))
    import parallel_eval

    jobs = {
        "jobs": [
            {"id": "l0", "args": ["--run-id", "l0"], "slot": "auto"},
            {"id": "l1", "args": ["--run-id", "l1"], "deps": ["l0"], "slot": "auto"},
            {"id": "g0", "args": ["--run-id", "g0"], "slot": "2"},
        ]
    }
    jf = tmp_path / "jobs.json"
    jf.write_text(json.dumps(jobs), "utf-8")
    ran = []
    rc = parallel_eval.main(
        [
            "--jobs",
            str(jf),
            "--state",
            str(tmp_path / "st.json"),
            "--base-dir",
            str(tmp_path),
            "--dry-run",
        ],
        runner=lambda a, s: ran.append(a) or 0,
    )
    plan = json.loads(capsys.readouterr().out)
    assert rc == 0 and ran == [] and not (tmp_path / "st.json").exists()
    assert [(p["job"], p["action"]) for p in plan] == [("l0", "run"), ("l1", "run"), ("g0", "run")]
    assert plan[2]["slot"] == "2" and plan[0]["slot"] in ("1", "2")


def test_cli_refuses_slot2_when_not_enabled(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(ROOT / "scripts"))
    import parallel_eval

    from traceforge.agent import axforge

    monkeypatch.setattr(axforge, "slot2_enabled", lambda: False)
    jf = tmp_path / "jobs.json"
    jf.write_text(json.dumps({"jobs": [{"id": "a", "args": ["x"]}]}), "utf-8")
    assert parallel_eval.main(["--jobs", str(jf), "--state", str(tmp_path / "s.json")]) == 2
    assert "slot 2" in capsys.readouterr().err
