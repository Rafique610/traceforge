"""Pool tests: fakes only, fake clock, no network, no provider calls."""

import json
import random

import pytest

from traceforge.agent import axforge, beatapi
from traceforge.agent.pool import Deferred, Pool, PoolRefused, Reply, Task


class Clock:
    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def make(tmp_path, send, clock, slot2=True, **kw):
    return Pool(
        tmp_path / "r" / "results.jsonl",
        send,
        clock=clock.now,
        sleep=clock.sleep,
        wall=clock.now,
        rng=random.Random(1),
        slot2_enabled=lambda: slot2,
        halted_probe=lambda n: None,
        **kw,
    )


def tasks(n, allow=True):
    return [
        Task(f"t{i}", [{"role": "user", "content": str(i)}], allow_axforge=allow) for i in range(n)
    ]


def rows(pool):
    return [json.loads(x) for x in pool.results_path.read_text("utf-8").splitlines()]


def fake_send(clock, log, latency=2.0, fail=None):
    def send(provider, task):
        log.append((provider, task.task_id, clock.now()))
        clock.t += latency
        if fail and fail(provider, task):
            raise RuntimeError("boom")
        model = beatapi.FREE_MODEL if provider == "beatapi" else axforge.MODEL
        return Reply("ok", 10, 5, model)

    return send


def test_routing_dev_beatapi_first_and_spill_only_if_allowed(tmp_path):
    c, log = Clock(), []
    p = make(tmp_path, fake_send(c, log), c)
    for t in tasks(2, allow=False):
        p.submit(t)
    p.run(threaded=False)
    assert {x[0] for x in log} == {"beatapi"}  # not allowed to spill
    c2, log2 = Clock(), []
    p2 = make(tmp_path / "b", fake_send(c2, log2), c2)
    for t in tasks(6, allow=True):
        p2.submit(t)
    p2.run(threaded=False)
    assert log2[0][0] == "beatapi"
    assert {x[0] for x in log2} == {"beatapi", "axforge1", "axforge2"}
    assert len(rows(p2)) == 6


def test_slot2_only_when_enabled(tmp_path):
    c = Clock()
    p = make(tmp_path, fake_send(c, []), c, slot2=False)
    assert set(p.providers) == {"beatapi", "axforge1"}


def test_official_refused(tmp_path):
    c = Clock()
    p = make(tmp_path, fake_send(c, []), c)
    with pytest.raises(PoolRefused):
        p.submit(Task("x", [], official=True))
    assert not p.results_path.exists()


def test_rows_record_provider_model_tier(tmp_path):
    c = Clock()
    p = make(tmp_path, fake_send(c, []), c)
    for t in tasks(3):
        p.submit(t)
    p.run(threaded=False)
    for r in rows(p):
        assert r["tier"] == "development"
        assert r["provider"] in {"beatapi", "axforge1", "axforge2"}
        want = beatapi.FREE_MODEL if r["provider"] == "beatapi" else axforge.MODEL
        assert r["model"] == want


def test_no_duplicates_after_restart(tmp_path):
    c, log = Clock(), []
    p = make(tmp_path, fake_send(c, log), c)
    for t in tasks(4):
        p.submit(t)
    p.run(threaded=False)
    n = len(log)
    c2, log2 = Clock(), []
    p2 = make(tmp_path, fake_send(c2, log2), c2)
    assert not any(p2.submit(t) for t in tasks(4))  # all skipped
    assert p2.submit(Task("new", [])) is True
    p2.run(threaded=False)
    assert n == 4 and [x[1] for x in log2] == ["new"]
    assert len({r["key"] for r in rows(p2)}) == 5


def test_torn_line_ignored_on_restart(tmp_path):
    c = Clock()
    p = make(tmp_path, fake_send(c, []), c)
    p.submit(tasks(1)[0])
    p.run(threaded=False)
    with p.results_path.open("a", encoding="utf-8") as f:
        f.write('{"key": "abc", "ok": tr')
    p2 = make(tmp_path, fake_send(c, []), c)
    assert len(p2._done) == 1


def test_failure_halts_provider_and_reroutes_pending(tmp_path):
    c, log = Clock(), []
    send = fake_send(c, log, fail=lambda prov, t: prov == "beatapi")
    p = make(tmp_path, send, c)
    for t in tasks(4):
        p.submit(t)
    st = p.run(threaded=False)
    assert [x for x in log if x[0] == "beatapi"] == [log[0]]  # one attempt, no retry
    assert st["providers"]["beatapi"]["halted"] and st["providers"]["beatapi"]["failures"] == 1
    failed = [r for r in rows(p) if not r["ok"]][0]["task_id"]
    ok_ids = {r["task_id"] for r in rows(p) if r["ok"]}
    assert failed not in ok_ids  # failed task not retried
    assert ok_ids == {"t0", "t1", "t2", "t3"} - {failed}
    assert all(r["provider"] != "beatapi" for r in rows(p) if r["ok"])


def test_failure_without_allow_leaves_tasks_pending(tmp_path):
    c = Clock()
    p = make(tmp_path, fake_send(c, [], fail=lambda prov, t: True), c)
    for t in tasks(3, allow=False):
        p.submit(t)
    st = p.run(threaded=False)
    assert len(st["pending"]) == 2 and st["combined"]["requests"] == 0


def test_pacing_intervals_with_fake_clock(tmp_path):
    c, log = Clock(), []
    p = make(tmp_path, fake_send(c, log, latency=1.0), c)
    for t in tasks(9):
        p.submit(t)
    p.run(threaded=False)
    for name, floor in (
        ("beatapi", beatapi.MIN_INTERVAL_S),
        ("axforge1", axforge.MIN_START_INTERVAL_S),
        ("axforge2", axforge.MIN_START_INTERVAL_S),
    ):
        starts = [x[2] for x in log if x[0] == name]
        assert len(starts) >= 1
        assert all(b - a >= floor for a, b in zip(starts, starts[1:], strict=False)), name


def test_deferred_backs_off_without_failing_or_retrying_failure(tmp_path):
    c, calls = Clock(), []

    def send(provider, task):
        calls.append(c.now())
        if len(calls) <= 2:
            raise Deferred("retry-after not elapsed")
        return Reply("ok", 1, 1, beatapi.FREE_MODEL)

    p = make(tmp_path, send, c, jitter_max=0.0)
    p.submit(tasks(1, allow=False)[0])
    st = p.run(threaded=False)
    assert st["combined"]["requests"] == 1 and st["combined"]["failures"] == 0
    assert calls[1] - calls[0] == beatapi.MIN_INTERVAL_S  # exponential: x1 then x2
    assert calls[2] - calls[1] == beatapi.MIN_INTERVAL_S * 2


def test_stats(tmp_path):
    c = Clock()
    lat = iter([1.0, 3.0, 5.0])

    def send(provider, task):
        c.t += next(lat)
        return Reply("ok", 100, 50, beatapi.FREE_MODEL)

    p = make(tmp_path, send, c, jitter_max=0.0)
    for t in tasks(3, allow=False):
        p.submit(t)
    st = p.run(threaded=False)
    b = st["providers"]["beatapi"]
    assert b["requests"] == 3 and b["tokens_in"] == 300 and b["tokens_out"] == 150
    assert b["latency_p50_s"] == 3.0 and b["latency_p95_s"] == 5.0
    assert b["rpm"] == pytest.approx(3 / (2 * 90 + 5) * 60)
    comb = st["combined"]
    assert comb["requests"] == 3 and comb["tokens_in"] == 300 and comb["failures"] == 0
    assert st["providers"]["axforge1"]["requests"] == 0


def test_threaded_smoke_no_duplicates(tmp_path):
    import time as _t

    def send(provider, task):
        return Reply("ok", 1, 1, None)

    p = Pool(
        tmp_path / "r.jsonl",
        send,
        slot2_enabled=lambda: True,
        halted_probe=lambda n: None,
        sleep=lambda s: _t.sleep(0.001),
        poll_s=0.001,
        jitter_max=0.0,
    )
    for prov in p.providers.values():
        prov.interval = 0.0
    for t in tasks(12):
        p.submit(t)
    p.run()
    keys = [r["key"] for r in rows(p)]
    assert len(keys) == len(set(keys)) == 12
