"""BeatAPI shared-account safety: one run at a time, atomic cross-process pacing, halt on the first
failure, stable state location. No network: only fake clients and local helper processes."""

import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest
from test_beatapi import FakeClient, settings

from traceforge.agent import beatapi
from traceforge.agent.gateway import GatewayError, chat

BACKEND = Path(__file__).resolve().parents[2]
PY = sys.executable


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    monkeypatch.setattr(beatapi, "LEDGER", tmp_path / "ledger.jsonl")
    beatapi.reset_halt()
    yield
    beatapi.reset_halt()


def spawn(code: str, *args: str, cwd: Path | None = None) -> subprocess.Popen:
    return subprocess.Popen(
        [PY, "-c", textwrap.dedent(code), *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd or BACKEND,
    )


HOLD_RUN_LOCK = """
import sys
from pathlib import Path
from traceforge.agent import beatapi
with beatapi.single_instance(Path(sys.argv[1]), label="holder"):
    print("ready", flush=True)
    sys.stdin.readline()
"""


def wait_ready(p: subprocess.Popen) -> None:
    assert p.stdout.readline().strip() == "ready", p.stderr.read()


def stop(p: subprocess.Popen) -> None:
    try:
        p.stdin.write("\n")
        p.stdin.flush()
    except OSError:
        pass
    p.wait(timeout=20)


# --- 1. single instance -----------------------------------------------------------------------
def test_second_run_is_refused_while_the_first_holds_the_lock(tmp_path):
    lock = tmp_path / "run.lock"
    p = spawn(HOLD_RUN_LOCK, str(lock))
    try:
        wait_ready(p)
        with pytest.raises(beatapi.BeatApiBusy, match="already active.*holder"):
            with beatapi.single_instance(lock):
                pytest.fail("a second run must never start")
    finally:
        stop(p)


def test_lock_is_released_after_normal_exit_and_reusable(tmp_path):
    lock = tmp_path / "run.lock"
    with beatapi.single_instance(lock):
        pass
    with beatapi.single_instance(lock):  # no stale lock after a normal completion
        pass


def test_lock_is_released_when_the_holder_is_killed(tmp_path):
    lock = tmp_path / "run.lock"
    p = spawn(HOLD_RUN_LOCK, str(lock))
    wait_ready(p)
    with pytest.raises(beatapi.BeatApiBusy):
        with beatapi.single_instance(lock):
            pass
    p.kill()  # no cleanup code runs: the OS drops the lock with the process
    p.wait(timeout=20)
    with beatapi.single_instance(lock):
        pass


def test_runner_cli_refuses_a_second_beatapi_launch_with_exit_3(tmp_path, monkeypatch):
    from traceforge.evaluation import runner

    lock = tmp_path / "run.lock"
    monkeypatch.setattr(beatapi, "RUN_LOCK_FILE", lock)
    p = spawn(HOLD_RUN_LOCK, str(lock))
    try:
        wait_ready(p)
        calls = []
        monkeypatch.setattr(runner, "run_experiment", lambda *a, **k: calls.append(1))
        rc = runner.main(
            [
                "--manifest",
                str(BACKEND.parent / "datasets" / "manifests" / "dev.json"),
                "--condition",
                "L0",
                "--run-id",
                "x",
                "--provider",
                "beatapi",
                "--model",
                "glm-5.3-flash-free",
            ]
        )
        assert rc == 3 and calls == []  # refused before anything ran
    finally:
        stop(p)


# --- 2. atomic pacing across processes ---------------------------------------------------------
PACED_REQUEST = """
import sys, time, json
from pathlib import Path
from traceforge.agent import beatapi
beatapi.MIN_INTERVAL_S = float(sys.argv[2])
state = Path(sys.argv[1])
print("ready", flush=True)
sys.stdin.readline()
beatapi.pace(state_file=state)
sent = time.time()
time.sleep(float(sys.argv[3]))          # the request is "in flight"
beatapi.stamp_done(state_file=state)
print(json.dumps({"sent": sent, "done": time.time()}), flush=True)
"""


def test_two_processes_cannot_bypass_pacing_or_overlap(tmp_path):
    state = tmp_path / "state.json"
    interval, work = 1.5, 0.6
    procs = [spawn(PACED_REQUEST, str(state), str(interval), str(work)) for _ in range(2)]
    for p in procs:
        wait_ready(p)
    for p in procs:  # release both at the same moment
        p.stdin.write("\n")
        p.stdin.flush()
    spans = sorted(
        (json.loads(p.stdout.readline()) for p in procs),
        key=lambda r: r["sent"],
    )
    for p in procs:
        p.wait(timeout=30)
    first, second = spans
    assert second["sent"] >= first["done"] + interval - 0.15  # spacing counted from completion
    assert second["sent"] >= first["sent"] + work  # never in flight together


def test_killed_requester_frees_the_request_slot(tmp_path):
    state = tmp_path / "state.json"
    hold = """
    import sys
    from pathlib import Path
    from traceforge.agent import beatapi
    beatapi.pace(state_file=Path(sys.argv[1]))   # takes the slot, never finishes
    print("ready", flush=True)
    sys.stdin.readline()
    """
    p = spawn(hold, str(state))
    wait_ready(p)
    lock = beatapi.FileLock(state.with_suffix(".lock"))
    assert not lock.try_acquire()  # held while the request is "in flight"
    p.kill()
    p.wait(timeout=20)
    assert lock.try_acquire()  # recovered: nothing stale
    lock.release()


def test_interval_is_90_seconds_and_state_survives_between_calls(tmp_path):
    assert beatapi.MIN_INTERVAL_S == 90.0
    state = tmp_path / "s.json"
    t = {"now": 5000.0}
    beatapi.pace(sleep=lambda s: None, now=lambda: t["now"], state_file=state)
    t["now"] = 5010.0
    beatapi.stamp_done(now=lambda: t["now"], state_file=state)
    assert beatapi.seconds_until_allowed(5030.0, state) == pytest.approx(70.0)


# --- 3. first provider failure halts BeatAPI ---------------------------------------------------
@pytest.mark.parametrize("status", [429, 503, 500])
def test_first_provider_failure_stops_all_further_calls(tmp_path, monkeypatch, status):
    monkeypatch.setattr(beatapi, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(beatapi.time, "sleep", lambda s: None)
    client = FakeClient(fail_status=status)
    s = settings(tmp_path)
    msgs = [{"role": "user", "content": "x"}]
    with pytest.raises(GatewayError, match=str(status)):
        chat(msgs, settings=s, client=client, use_cache=False)
    for _ in range(5):  # callers that retry or continue get no further network calls
        with pytest.raises(GatewayError, match="halted after the first provider failure"):
            chat(msgs, settings=s, client=client, use_cache=False)
    assert len(client.calls) == 1
    assert beatapi.halted() is not None
    assert not (tmp_path / "ledger.jsonl").exists()  # a failed request is no completed usage


def test_halt_does_not_touch_other_providers():
    beatapi.halt("503")
    from traceforge.agent import axforge

    assert hasattr(axforge, "reserve")  # separate module; its gateway path never reads the halt
    import inspect

    from traceforge.agent import gateway

    assert "beatapi.halted" not in inspect.getsource(gateway._call_axforge)


def test_pipeline_failure_after_halt_is_a_provider_error_with_one_request(tmp_path, monkeypatch):
    """diagnose retries on GatewayError; with BeatAPI halted those retries cost no requests."""
    monkeypatch.setattr(beatapi, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(beatapi.time, "sleep", lambda s: None)
    from traceforge.agent.pipeline import run_case, sample_sources

    src = sample_sources()
    client = FakeClient(fail_status=503)
    s = settings(tmp_path)

    def chat_fn(messages, tools):
        return chat(messages, tools=tools, settings=s, client=client, use_cache=False)

    rec = run_case(src.cases.get("code"), "L0", src, chat_fn=chat_fn, settings=s)
    assert rec.failure_reason.startswith("provider_error")
    assert len(client.calls) == 1 and rec.outcome == "NO_PATCH"


# --- 4. stable state location ------------------------------------------------------------------
def test_state_is_anchored_at_the_repository_root_from_any_working_directory(tmp_path):
    code = "from traceforge.agent import beatapi as b; print(b.STATE_FILE); print(b.RUN_LOCK_FILE)"
    outs = []
    for cwd in (BACKEND, tmp_path, BACKEND.parent):
        r = subprocess.run(
            [PY, "-c", code],
            cwd=cwd,
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONPATH": str(BACKEND)},
        )
        assert r.returncode == 0, r.stderr
        outs.append(r.stdout)
    assert outs[0] == outs[1] == outs[2]
    state, lock = outs[0].splitlines()
    assert Path(state).is_absolute() and Path(state).parent == BACKEND.parent / ".cache"
    assert Path(lock).parent == BACKEND.parent / ".cache"


def test_pacing_state_is_shared_between_different_working_directories(tmp_path):
    """Two processes started from different directories still serialise on the same state."""
    state = tmp_path / "state.json"
    a = spawn(PACED_REQUEST, str(state), "1.0", "0.3", cwd=BACKEND)
    b = spawn(PACED_REQUEST, str(state), "1.0", "0.3", cwd=tmp_path)
    env_ok = True
    for p in (a, b):
        line = p.stdout.readline().strip()
        env_ok &= line == "ready"
    if not env_ok:  # cwd outside the backend cannot import the package without PYTHONPATH
        for p in (a, b):
            p.kill()
        pytest.skip("package not importable from a foreign cwd in this environment")
    for p in (a, b):
        p.stdin.write("\n")
        p.stdin.flush()
    spans = sorted((json.loads(p.stdout.readline()) for p in (a, b)), key=lambda r: r["sent"])
    for p in (a, b):
        p.wait(timeout=30)
    assert spans[1]["sent"] >= spans[0]["done"] + 1.0 - 0.15


def test_legacy_state_is_migrated_once(tmp_path, monkeypatch):
    legacy, new = tmp_path / "legacy.json", tmp_path / "new" / "state.json"
    legacy.write_text(json.dumps({"sent_at": 1.0, "done_at": 2.0}))
    monkeypatch.setattr(beatapi, "LEGACY_STATE_FILE", legacy)
    monkeypatch.setattr(beatapi, "STATE_FILE", new)
    beatapi._migrate_legacy()
    assert json.loads(new.read_text())["done_at"] == 2.0
    new.write_text(json.dumps({"done_at": 9.0}))
    beatapi._migrate_legacy()  # never overwrites newer state
    assert json.loads(new.read_text())["done_at"] == 9.0
    assert time.time() > 0
