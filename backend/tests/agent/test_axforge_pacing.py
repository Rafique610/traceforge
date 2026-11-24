"""AxForge pacing: 2 requests per minute, shared by threads and processes; 429 stops the run.

No network and no real state: fake clients, temporary ledgers and a temporary pacing file."""

import inspect
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace as N

import pytest

from traceforge.agent import axforge, beatapi, gateway
from traceforge.agent.gateway import GatewayError

BACKEND = Path(__file__).resolve().parents[2]
CALL = {"model": axforge.MODEL, "messages": [{"role": "user", "content": "x"}], "max_tokens": 100}


@pytest.fixture(autouse=True)
def ledger(monkeypatch, tmp_path):
    path = tmp_path / "usage.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(axforge, "LEDGER", path)
    monkeypatch.setattr(axforge, "PACING_FILE", tmp_path / "pacing.json")
    monkeypatch.setattr(axforge, "_authorized_by", "test-run")
    monkeypatch.setattr(axforge, "MIN_START_INTERVAL_S", 30.0)  # the real production value
    return path


class Clock:
    """Controllable wall clock: sleep() advances it, so waits are exact and instant."""

    def __init__(self, t=100_000.0):
        self.t, self.slept = t, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def err429(headers=None):
    e = RuntimeError("rate limited")
    e.status_code = 429
    e.response = N(headers=headers or {})
    return e


class Client:
    def __init__(self, fail=None):
        self.calls, self.fail = 0, fail
        self.chat = N(completions=N(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        if self.fail:
            raise self.fail
        return N(
            choices=[N(message=N(content="OK", tool_calls=None), finish_reason="stop")],
            usage=N(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )


def ledger_rows(path):
    return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]


# --- the interval is measured start to start --------------------------------------------------


def test_the_limit_is_two_requests_per_minute():
    assert axforge.MIN_START_INTERVAL_S == 30.0  # not the old 10 s completion-based gap


def test_interval_counts_from_the_previous_start_not_its_completion():
    c = Clock()
    assert axforge.pace(c.sleep, c.now) == 0  # nothing before: no wait
    start1 = c.t
    c.t += 20  # the request takes 20 s
    axforge.done_turn(c.now)
    c.t += 1  # next request is wanted 21 s after the first STARTED
    waited = axforge.pace(c.sleep, c.now)
    assert waited == pytest.approx(9.0)  # 30 - 21: the completion time is not the reference
    assert c.t - start1 == pytest.approx(30.0)
    axforge.done_turn(c.now)


def test_a_slow_request_does_not_add_a_wait_beyond_the_interval():
    c = Clock()
    axforge.pace(c.sleep, c.now)
    c.t += 95  # a slow generation: longer than the interval
    axforge.done_turn(c.now)
    assert axforge.pace(c.sleep, c.now) == 0
    axforge.done_turn(c.now)


def test_a_new_process_honours_the_shared_state_of_the_previous_one():
    c = Clock()
    axforge.pace(c.sleep, c.now)
    axforge.done_turn(c.now)
    # simulate a brand-new process: nothing in memory, only the state file remains
    c.t += 5
    assert axforge.pace(c.sleep, c.now) == pytest.approx(25.0)
    axforge.done_turn(c.now)


def test_a_failed_request_keeps_the_spacing_and_unreadable_state_fails_closed():
    c = Clock()
    axforge.pace(c.sleep, c.now)
    axforge.done_turn(c.now)  # (a failed request also stamped its start before sending)
    c.t += 1
    assert axforge.pace(c.sleep, c.now) == pytest.approx(29.0)
    axforge.done_turn(c.now)
    axforge.PACING_FILE.write_text("{not json", encoding="utf-8")
    assert axforge.pace(c.sleep, c.now) == pytest.approx(30.0)  # unreadable: wait a full interval
    axforge.done_turn(c.now)


def test_a_backwards_clock_jump_cannot_stall_beyond_one_interval():
    c = Clock()
    axforge.pace(c.sleep, c.now)
    axforge.done_turn(c.now)
    c.t -= 3600  # wall clock jumped back an hour
    assert axforge.pace(c.sleep, c.now) == pytest.approx(30.0)
    axforge.done_turn(c.now)


# --- workers and processes cannot bypass it ---------------------------------------------------


def test_parallel_workers_in_one_process_are_serialised_and_spaced(monkeypatch):
    monkeypatch.setattr(axforge, "MIN_START_INTERVAL_S", 0.4)  # real time, short interval
    starts, lock = [], threading.Lock()

    def worker():
        axforge.pace()  # real clock and real sleep
        with lock:
            starts.append(time.time())
        time.sleep(0.05)  # the "request"
        axforge.done_turn()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    starts.sort()
    assert len(starts) == 4
    assert all(b - a >= 0.4 - 0.05 for a, b in zip(starts, starts[1:], strict=False))


PROC = """
import sys, time
from pathlib import Path
from traceforge.agent import axforge
axforge.PACING_FILE = Path(sys.argv[1])
axforge.MIN_START_INTERVAL_S = float(sys.argv[2])
axforge.pace()
print(time.time(), flush=True)
time.sleep(0.2)
axforge.done_turn()
"""


def test_separate_processes_share_one_interval(tmp_path):
    state = tmp_path / "shared.json"
    procs = [
        subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", PROC, str(state), "1.5"],
            cwd=BACKEND,
            stdout=subprocess.PIPE,
            text=True,
        )  # fmt: skip
        for _ in range(3)
    ]
    starts = sorted(float(p.communicate(timeout=60)[0]) for p in procs)
    assert len(starts) == 3
    assert all(b - a >= 1.5 - 0.1 for a, b in zip(starts, starts[1:], strict=False)), starts
    assert starts[-1] - starts[0] >= 2 * 1.5 - 0.2


def test_the_axforge_rule_is_not_applied_to_beatapi(monkeypatch):
    assert "axforge" not in inspect.getsource(gateway._call_beatapi)
    assert beatapi.MIN_INTERVAL_S == 90.0  # BeatAPI keeps its own, unchanged rule
    monkeypatch.setattr(axforge, "pace", lambda *a, **k: pytest.fail("BeatAPI used AxForge pacing"))
    monkeypatch.setattr(beatapi, "pace", lambda *a, **k: 0)
    monkeypatch.setattr(beatapi, "stamp_done", lambda *a, **k: None)
    monkeypatch.setattr(beatapi, "record_usage", lambda *a, **k: None)
    monkeypatch.setattr(beatapi, "_halt_reason", None)
    c = Client()
    gateway._call_beatapi(c, {"model": beatapi.FREE_MODEL, "messages": []})
    assert c.calls == 1


# --- 429: stop at once, record everything, never retry, respect Retry-After --------------------


def test_first_429_stops_immediately_and_is_never_retried(ledger):
    c = Client(fail=err429({"Retry-After": "120"}))
    with pytest.raises(GatewayError, match=r"failed \(429\).*not retried"):
        gateway._call_axforge(c, dict(CALL))
    assert c.calls == 1 and axforge.halted() is not None
    for _ in range(3):  # a caller that tries again is refused locally: no further request
        with pytest.raises(GatewayError, match="halted after the first provider failure"):
            gateway._call_axforge(c, dict(CALL))
    assert c.calls == 1


def test_429_records_status_time_headers_and_retry_after_with_secrets_redacted(ledger):
    headers = {
        "Retry-After": "120", "X-RateLimit-Remaining": "0", "Date": "Tue, 24 Nov 2026 12:00:00 GMT",
        "Authorization": "Bearer sk-supersecretvalue123", "Set-Cookie": "session=abc",
        "X-Debug": "key sk-abcdefghijkl leaked",
    }  # fmt: skip
    before = time.time()
    with pytest.raises(GatewayError):
        gateway._call_axforge(Client(fail=err429(headers)), dict(CALL))
    row = [r for r in ledger_rows(ledger) if r["type"] == "error"][0]
    assert row["http_status"] == 429 and row["ts"] >= before and row["retry_after_s"] == 120.0
    assert row["headers"]["retry-after"] == "120" and row["headers"]["x-ratelimit-remaining"] == "0"
    assert "authorization" not in row["headers"] and "set-cookie" not in row["headers"]
    assert "sk-abcdefghijkl" not in json.dumps(row) and "supersecret" not in json.dumps(row)
    state = json.loads(axforge.PACING_FILE.read_text("utf-8"))
    assert state["last_429"]["retry_after_s"] == 120.0 and state["blocked_until"] >= before + 119


def test_retry_after_forms_and_absence():
    assert axforge.parse_retry_after("45") == 45.0
    assert axforge.parse_retry_after("Tue, 24 Nov 2026 12:01:00 GMT", 1795608000.0) is not None
    assert axforge.parse_retry_after(None) is None and axforge.parse_retry_after("soon") is None
    c = Client(fail=err429({}))  # no Retry-After: recorded as unknown, nothing blocks
    with pytest.raises(GatewayError):
        gateway._call_axforge(c, dict(CALL))
    state = json.loads(axforge.PACING_FILE.read_text("utf-8"))
    assert state["last_429"]["retry_after_s"] is None and "blocked_until" not in state


def test_retry_after_is_respected_by_a_later_attempt_and_sends_nothing(monkeypatch):
    clock = Clock(5000.0)
    fake = N(time=clock.now, sleep=clock.sleep, strftime=time.strftime, localtime=time.localtime)
    monkeypatch.setattr(axforge, "time", fake)
    with pytest.raises(GatewayError):
        gateway._call_axforge(Client(fail=err429({"Retry-After": "300"})), dict(CALL))
    axforge.reset_halt()  # a later, manually authorised attempt in a new process
    clock.t += 100  # only 100 s of the 300 s have passed
    c = Client()
    with pytest.raises(GatewayError, match="last 429 asked to wait until"):
        gateway._call_axforge(c, dict(CALL))
    assert c.calls == 0 and axforge._inflight == 0 and axforge._slot_file is None
    assert clock.slept == []  # it refuses; it never sleeps through a Retry-After
    clock.t += 250  # now past Retry-After: allowed again (and paced)
    gateway._call_axforge(c, dict(CALL))
    assert c.calls == 1


def test_pace_stops_runs_through_the_normal_chat_path_without_a_second_request(ledger):
    from traceforge.config import Settings

    c = Client(fail=err429({"Retry-After": "60"}))
    s = Settings(llm_provider="axforge", llm_model="glm-5.3-flash", axforge_api_key="k")
    for _ in range(3):  # the diagnose loop may call chat again after a failure
        with pytest.raises(GatewayError):
            gateway.chat([{"role": "user", "content": "x"}], settings=s, client=c, use_cache=False)
    assert c.calls == 1  # exactly one network request across all of them
    assert len([r for r in ledger_rows(ledger) if r["type"] == "error"]) == 1


def test_every_request_start_is_logged_so_the_interval_can_be_audited():
    c = Clock()
    for _ in range(3):
        axforge.pace(c.sleep, c.now)
        c.t += 3  # a short request
        axforge.done_turn(c.now)
    log = axforge.PACING_FILE.with_suffix(".log.jsonl")
    rows = [json.loads(x) for x in log.read_text("utf-8").splitlines()]
    sent = [r["sent_at"] for r in rows]
    assert len(rows) == 3 and rows[0]["prev_start"] is None
    assert all(b - a >= 30.0 - 1e-6 for a, b in zip(sent, sent[1:], strict=False))
    assert rows[1]["prev_start"] == sent[0] and rows[1]["waited_s"] == pytest.approx(27.0)
