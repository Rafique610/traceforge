"""Two AxForge key slots: independent ledgers, pacing, halts, ceilings; slot 2 owner-gated.

Fakes only: no network, no real key (a sentinel value stands in), temporary files."""

import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace as N

import pytest

from traceforge.agent import axforge, gateway
from traceforge.agent.gateway import GatewayError
from traceforge.config import Settings

BACKEND = Path(__file__).resolve().parents[2]
SENTINEL = "sk-SENTINEL-do-not-leak-0123456789"
SENTINEL1 = "sk-SENTINEL-slot-one-9876543210"
CALL = {"model": axforge.MODEL, "messages": [{"role": "user", "content": "x"}], "max_tokens": 100}


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    for name in ("LEDGER", "LEDGER2"):
        p = tmp_path / f"{name}.jsonl"
        p.write_text("", encoding="utf-8")
        monkeypatch.setattr(axforge, name, p)
    monkeypatch.setattr(axforge, "PACING_FILE", tmp_path / "pacing.json")
    monkeypatch.setattr(axforge, "PACING_FILE2", tmp_path / "pacing_k2.json")
    monkeypatch.setattr(axforge, "ENABLE_MARKER", tmp_path / "keys_verified.json")
    monkeypatch.setattr(axforge, "_authorized_by", "test-run")
    monkeypatch.setattr(axforge, "MIN_START_INTERVAL_S", 30.0)
    monkeypatch.setattr(axforge, "_inflight", 0)
    monkeypatch.setitem(axforge._k2, "inflight", 0)
    monkeypatch.setitem(axforge._k2, "halt", None)
    monkeypatch.setattr(axforge, "_halt_reason", None)
    monkeypatch.setitem(Settings.model_config, "env_file", None)  # never read the real .env
    monkeypatch.setenv("AXFORGE_API_KEY", SENTINEL1)
    monkeypatch.delenv("AXFORGE_API_KEY2", raising=False)
    monkeypatch.delenv("TRACEFORGE_AXFORGE_KEY_SLOT", raising=False)
    return tmp_path


def enable(tmp_path, monkeypatch, flag=True):
    monkeypatch.setenv("AXFORGE_API_KEY2", SENTINEL)
    (tmp_path / "keys_verified.json").write_text(json.dumps({"slot2_enabled": flag}), "utf-8")


class Clock:
    def __init__(self, t=100_000.0):
        self.t, self.slept = t, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class Client:
    def __init__(self, fail=None, hold=0.0, tracker=None, name=""):
        self.calls, self.fail, self.hold, self.tracker, self.name = 0, fail, hold, tracker, name
        self.chat = N(completions=N(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        if self.tracker is not None:
            self.tracker.enter(self.name)
        try:
            time.sleep(self.hold)
            if self.fail:
                raise self.fail
            return N(
                choices=[N(message=N(content="OK", tool_calls=None), finish_reason="stop")],
                usage=N(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
        finally:
            if self.tracker is not None:
                self.tracker.leave(self.name)


class Tracker:
    def __init__(self):
        self.lock, self.now, self.max_per, self.max_all = threading.Lock(), {}, {}, 0

    def enter(self, name):
        with self.lock:
            self.now[name] = self.now.get(name, 0) + 1
            self.max_per[name] = max(self.max_per.get(name, 0), self.now[name])
            self.max_all = max(self.max_all, sum(self.now.values()))

    def leave(self, name):
        with self.lock:
            self.now[name] -= 1


def err429(headers=None):
    e = RuntimeError("rate limited")
    e.status_code = 429
    e.response = N(headers=headers or {})
    return e


def rows(path):
    return [json.loads(x) for x in Path(path).read_text("utf-8").splitlines() if x.strip()]


# --- slot 2 is owner-gated ----------------------------------------------------------------


def test_slot2_refused_without_marker_or_env(env, monkeypatch):
    c = Client()
    with pytest.raises(axforge.AxForgeRefused, match="slot 2 is disabled"):
        axforge.reserve(500, slot="2")
    with pytest.raises(GatewayError, match="slot 2 is disabled"):
        gateway._call_axforge(c, dict(CALL), "2")
    monkeypatch.setenv("AXFORGE_API_KEY2", SENTINEL)  # env only, no marker
    assert not axforge.slot2_enabled()
    (env / "keys_verified.json").write_text('{"slot2_enabled": false}', "utf-8")
    assert not axforge.slot2_enabled()
    monkeypatch.delenv("AXFORGE_API_KEY2")  # marker true, no env
    (env / "keys_verified.json").write_text('{"slot2_enabled": true}', "utf-8")
    assert not axforge.slot2_enabled()
    assert c.calls == 0 and axforge._k2["inflight"] == 0


def test_make_client_uses_the_slots_key_and_refuses_slot2_when_disabled(env, monkeypatch):
    s2 = Settings(llm_provider="axforge", llm_model=axforge.MODEL, axforge_key_slot="2")
    with pytest.raises(axforge.AxForgeRefused):
        gateway.make_client(s2)
    enable(env, monkeypatch)
    s1 = Settings(llm_provider="axforge", llm_model=axforge.MODEL, axforge_key_slot="1")
    s2 = Settings(llm_provider="axforge", llm_model=axforge.MODEL, axforge_key_slot="2")
    assert gateway.make_client(s1).api_key == SENTINEL1
    assert gateway.make_client(s2).api_key == SENTINEL


def test_slot_setting_comes_from_the_environment(monkeypatch):
    assert Settings().axforge_key_slot == "1"
    monkeypatch.setenv("TRACEFORGE_AXFORGE_KEY_SLOT", "2")
    assert Settings().axforge_key_slot == "2"


# --- separate state --------------------------------------------------------------------------


def test_slot2_has_its_own_ledger_pacing_files_and_slot_name(env, monkeypatch):
    enable(env, monkeypatch)
    monkeypatch.setattr(axforge, "JITTER_MAX_S", 0.0)
    c = Client()
    gateway._call_axforge(c, dict(CALL), "2")
    r2 = rows(axforge.LEDGER2)
    assert r2[-1]["type"] == "request" and r2[-1]["slot"] == "2"
    assert rows(axforge.LEDGER) == []  # slot 1 ledger untouched
    log = rows(axforge.PACING_FILE2.with_suffix(".log.jsonl"))
    assert log[-1]["slot"] == "2" and not axforge.PACING_FILE.exists()
    assert axforge.totals(slot="2")["total_tokens"] == 15
    assert axforge.totals(slot="1")["total_tokens"] == 0
    assert axforge._floor_path(None, "2").name.endswith("LEDGER2.jsonl.floor")


def test_no_key_value_in_any_file_or_error_text(env, monkeypatch):
    enable(env, monkeypatch)
    monkeypatch.setattr(axforge, "JITTER_MAX_S", 0.0)
    gateway._call_axforge(Client(), dict(CALL), "2")
    with pytest.raises(GatewayError) as ei:
        gateway._call_axforge(Client(fail=err429({"retry-after": "5"})), dict(CALL), "1")
    texts = [str(ei.value)]
    with pytest.raises(GatewayError) as e2:
        gateway._call_axforge(Client(), dict(CALL), "1")  # halted now
    texts.append(str(e2.value))
    for f in env.iterdir():
        if f.is_file():
            texts.append(f.read_text("utf-8"))
    blob = "\n".join(texts)
    assert SENTINEL not in blob and SENTINEL1 not in blob and "SENTINEL" not in blob


# --- independent pacing and concurrency --------------------------------------------------------


def test_each_slot_is_paced_independently(env, monkeypatch):
    enable(env, monkeypatch)
    monkeypatch.setattr(axforge, "JITTER_MAX_S", 0.0)
    c = Clock()
    assert axforge.pace(c.sleep, c.now, slot="1") == 0
    axforge.done_turn(c.now, slot="1")
    c.t += 5
    assert axforge.pace(c.sleep, c.now, slot="2") == 0  # slot 1's start does not delay slot 2
    axforge.done_turn(c.now, slot="2")
    c.t += 5
    assert axforge.pace(c.sleep, c.now, slot="1") == pytest.approx(20.0)  # 30 - 10
    axforge.done_turn(c.now, slot="1")
    assert axforge.pace(c.sleep, c.now, slot="2") == pytest.approx(5.0)  # its own clock: 100005+30
    axforge.done_turn(c.now, slot="2")


def test_jitter_only_in_two_key_mode_and_rng_is_injectable(env, monkeypatch):
    c = Clock()
    rng = N(uniform=lambda a, b: 2.5)
    assert axforge.pace(c.sleep, c.now, slot="1", rng=rng) == 0  # slot 2 disabled: no jitter
    axforge.done_turn(c.now, slot="1")
    enable(env, monkeypatch)
    c.t += 100
    waited = axforge.pace(c.sleep, c.now, slot="1", rng=rng)
    assert waited == pytest.approx(2.5) and c.slept[-1] == pytest.approx(2.5)
    axforge.done_turn(c.now, slot="1")
    seen = []
    rng2 = N(uniform=lambda a, b: seen.append((a, b)) or 0.0)
    axforge.pace(c.sleep, c.now, slot="2", rng=rng2)
    axforge.done_turn(c.now, slot="2")
    assert seen == [(0.0, 3.0)]


def test_two_slots_run_concurrently_but_never_two_on_one_slot(env, monkeypatch):
    enable(env, monkeypatch)
    monkeypatch.setattr(axforge, "JITTER_MAX_S", 0.0)
    monkeypatch.setattr(axforge, "MIN_START_INTERVAL_S", 0.05)
    tr, errs = Tracker(), []

    def worker(slot):
        try:
            for _ in range(3):
                gateway._call_axforge(Client(hold=0.1, tracker=tr, name=slot), dict(CALL), slot)
        except Exception as e:  # pragma: no cover
            errs.append(e)

    ts = [threading.Thread(target=worker, args=(s,)) for s in ("1", "1", "2", "2")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs
    assert tr.max_per == {"1": 1, "2": 1}  # one in flight per key
    assert tr.max_all == 2  # the two keys overlapped
    assert axforge._inflight == 0 and axforge._k2["inflight"] == 0


# --- 429 / halt / Retry-After per slot ---------------------------------------------------------


def test_429_on_one_slot_halts_only_that_slot(env, monkeypatch):
    enable(env, monkeypatch)
    monkeypatch.setattr(axforge, "JITTER_MAX_S", 0.0)
    with pytest.raises(GatewayError, match="429"):
        gateway._call_axforge(Client(fail=err429()), dict(CALL), "2")
    assert axforge.halted("2") and axforge.halted("1") is None
    with pytest.raises(GatewayError, match="halted"):
        gateway._call_axforge(Client(), dict(CALL), "2")
    good = Client()
    gateway._call_axforge(good, dict(CALL), "1")
    assert good.calls == 1
    assert rows(axforge.LEDGER2)[-1]["http_status"] == 429
    assert [r for r in rows(axforge.LEDGER) if r["type"] == "error"] == []
    axforge.reset_halt("2")
    assert axforge.halted("2") is None


def test_retry_after_blocks_only_its_slot(env, monkeypatch):
    enable(env, monkeypatch)
    monkeypatch.setattr(axforge, "JITTER_MAX_S", 0.0)
    with pytest.raises(GatewayError):
        gateway._call_axforge(Client(fail=err429({"retry-after": "600"})), dict(CALL), "2")
    axforge.reset_halt("2")  # a new process would start clean; the block lives in the state file
    c2 = Client()
    with pytest.raises(GatewayError, match="Retry-After"):
        gateway._call_axforge(c2, dict(CALL), "2")
    assert c2.calls == 0 and axforge._k2["inflight"] == 0 and axforge._k2["file"] is None
    c1 = Client()
    gateway._call_axforge(c1, dict(CALL), "1")
    assert c1.calls == 1


# --- budget ----------------------------------------------------------------------------------


def fill(path, used):
    path.write_text(json.dumps({"type": "request", "total_tokens": used}) + "\n", "utf-8")


def test_per_slot_ceiling_is_independent(env, monkeypatch):
    enable(env, monkeypatch)
    monkeypatch.setattr(axforge, "JITTER_MAX_S", 0.0)
    fill(axforge.LEDGER2, 2_999_950)
    c2, c1 = Client(), Client()
    with pytest.raises(GatewayError, match="safety ceiling"):
        gateway._call_axforge(c2, dict(CALL), "2")
    gateway._call_axforge(c1, dict(CALL), "1")  # slot 1 has room: not affected by slot 2
    assert c2.calls == 0 and c1.calls == 1


def test_combined_ceiling_refuses_when_both_slots_together_would_cross(env, monkeypatch):
    enable(env, monkeypatch)
    monkeypatch.setattr(axforge, "JITTER_MAX_S", 0.0)
    fill(axforge.LEDGER, 2_500_000)
    fill(axforge.LEDGER2, 2_299_900)  # 4,799,900: each slot is fine alone
    for slot in ("1", "2"):
        c = Client()
        with pytest.raises(GatewayError, match="combined ceiling"):
            gateway._call_axforge(c, dict(CALL), slot)
        assert c.calls == 0
    assert axforge.COMBINED_CEILING == 4_800_000


def test_combined_ceiling_counts_other_slots_inflight_in_process(env, monkeypatch):
    enable(env, monkeypatch)
    fill(axforge.LEDGER, 2_000_000)
    fill(axforge.LEDGER2, 2_700_000)
    axforge.reserve(50_000, slot="2")  # 4,750,000 committed+inflight on slot 2's side
    with pytest.raises(axforge.AxForgeRefused, match="combined"):
        axforge.reserve(60_000, slot="1")
    axforge.release(50_000, "2")
    axforge.reserve(60_000, slot="1")
    axforge.release(60_000, "1")


def test_combined_ceiling_does_not_apply_when_slot2_is_disabled(env):
    fill(axforge.LEDGER, 2_000_000)
    fill(axforge.LEDGER2, 2_999_000)
    axforge.reserve(500, slot="1")
    axforge.release(500, "1")


def test_authorize_slot2_creates_its_ledger_only_when_enabled(env, monkeypatch):
    axforge.LEDGER2.unlink()
    with pytest.raises(axforge.AxForgeRefused):
        axforge.authorize("r", slot="2")
    assert not axforge.LEDGER2.exists()
    enable(env, monkeypatch)
    axforge.authorize("r", slot="2")
    assert rows(axforge.LEDGER2)[0]["slot"] == "2"


# --- report and runner -------------------------------------------------------------------------


def test_usage_report_has_per_slot_and_combined_blocks(env, monkeypatch):
    from traceforge.evaluation import usage_report

    axforge.LEDGER.write_text(
        json.dumps({"type": "request", "input_tokens": 600, "output_tokens": 400}) + "\n", "utf-8"
    )
    axforge.LEDGER2.write_text(
        json.dumps({"type": "request", "input_tokens": 10, "output_tokens": 5})
        + "\n"
        + json.dumps({"type": "error", "estimated_tokens": 40})
        + "\n",
        "utf-8",
    )
    rep = usage_report.report(beatapi_ledger=env / "none.jsonl")
    assert rep["axforge"]["committed_tokens"] == 1000  # slot 1 keys unchanged
    s2 = rep["axforge_slots"]["2"]
    assert s2["total_tokens"] == 15 and s2["estimated_tokens_failed_requests"] == 40
    assert s2["remaining_to_ceiling"] == 3_000_000 - 55 and s2["requests"] == 1
    comb = rep["axforge_combined"]
    assert comb["committed_tokens"] == 1055
    assert comb["remaining_to_ceiling"] == 4_800_000 - 1055 and comb["slot2_enabled"] is False


def test_runner_axforge_key_2_is_refused_unless_enabled_and_sets_the_slot(env, monkeypatch, capsys):
    from traceforge.evaluation import runner

    monkeypatch.setenv("TRACEFORGE_AXFORGE_KEY_SLOT", "1")  # restored after the test
    manifest = BACKEND.parent / "datasets" / "manifests" / "dev.json"
    base = ["--manifest", str(manifest), "--condition", "L0", "--run-id", "t", "--out", str(env)]
    args = [*base, "--axforge-billing-verified", "--axforge-key", "2"]
    seen = {}
    monkeypatch.setattr(runner, "run_experiment", lambda *a, **k: seen.update(k))
    from traceforge.config import get_settings

    try:
        assert runner.main(args) == 5 and not seen
        assert "slot 2 is disabled" in capsys.readouterr().err
        enable(env, monkeypatch)
        assert runner.main(args) == 0
        assert seen["axforge_slot"] == "2"
        assert rows(axforge.LEDGER2)[0]["type"] == "authorization"
    finally:
        get_settings.cache_clear()
