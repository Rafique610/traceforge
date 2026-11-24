import json
from types import SimpleNamespace as N

import pytest

from traceforge.agent import axforge, gateway


@pytest.fixture
def ledger(monkeypatch, tmp_path):
    path = tmp_path / "usage.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(axforge, "LEDGER", path)
    monkeypatch.setattr(axforge, "_authorized_by", "unit-test")  # gate: see test_axforge_gate.py
    return path


def _row(total, source="provider"):
    return json.dumps(
        {
            "type": "request",
            "input_tokens": total,
            "output_tokens": 0,
            "total_tokens": total,
            "usage_source": source,
        }
    )


class Client:
    def __init__(self, usage="default", err=None):
        if usage == "default":
            usage = N(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        self.calls, self.usage, self.err = 0, usage, err
        self.chat = N(completions=N(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        if self.err:
            raise self.err
        return N(
            choices=[N(message=N(content="OK", tool_calls=None), finish_reason="stop")],
            usage=self.usage,
        )


def test_usage_is_recorded_from_provider_and_accumulates(ledger):
    c = Client()
    for _ in range(2):
        gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 100})
    t = axforge.totals()
    assert (t["requests"], t["input_tokens"], t["output_tokens"], t["total_tokens"]) == (
        2,
        20,
        10,
        30,
    )
    assert t["reliable"] and t["remaining_to_ceiling"] == axforge.SAFETY_CEILING - 30


def test_stops_at_ceiling_and_sends_nothing(ledger):
    ledger.write_text(_row(axforge.SAFETY_CEILING) + "\n", encoding="utf-8")
    c = Client()
    with pytest.raises(gateway.GatewayError, match="safety ceiling"):
        gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 10})
    assert c.calls == 0


def test_request_that_could_cross_ceiling_is_refused(ledger):
    ledger.write_text(_row(axforge.SAFETY_CEILING - 5000) + "\n", encoding="utf-8")
    c = Client()
    with pytest.raises(gateway.GatewayError, match="safety ceiling"):
        gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 8000})
    assert c.calls == 0
    gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 1000})
    assert c.calls == 1


def test_missing_or_corrupt_ledger_stops(ledger):
    ledger.write_text("{not json\n", encoding="utf-8")
    c = Client()
    with pytest.raises(gateway.GatewayError, match="unreadable"):
        gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 10})
    ledger.unlink()
    with pytest.raises(gateway.GatewayError, match="missing"):
        gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 10})
    assert c.calls == 0


def test_unknown_usage_is_marked_unknown_and_then_stops(ledger):
    c = Client(usage=None)
    gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 10})
    t = axforge.totals()
    assert t["unknown_requests"] == 1 and not t["reliable"] and t["total_tokens"] == 0
    with pytest.raises(gateway.GatewayError, match="unknown usage"):
        gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 10})
    assert c.calls == 1


@pytest.mark.parametrize("status", [402, 403])
def test_billing_signal_stops_all_further_requests(ledger, status):
    err = RuntimeError("x")
    err.status_code = status
    c = Client(err=err)
    with pytest.raises(gateway.GatewayError, match="not retried"):
        gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 10})
    with pytest.raises(gateway.GatewayError, match="halted after the first provider failure"):
        gateway._call_axforge(Client(), {"model": axforge.MODEL, "max_tokens": 10})
    axforge.reset_halt()  # even a fresh process is stopped by the ledger's recorded stop
    with pytest.raises(gateway.GatewayError, match="stop was recorded"):
        gateway._call_axforge(Client(), {"model": axforge.MODEL, "max_tokens": 10})


def test_other_errors_are_logged_but_not_a_stop(ledger):
    err = RuntimeError("x")
    err.status_code = 503
    with pytest.raises(gateway.GatewayError):
        gateway._call_axforge(Client(err=err), {"model": axforge.MODEL, "max_tokens": 10})
    t = axforge.totals()
    assert not t["stopped"] and t["requests"] == 0


def test_cache_hits_never_touch_the_ledger(ledger, tmp_path):
    from traceforge.config import Settings

    s = Settings(
        llm_provider="axforge",
        llm_model=axforge.MODEL,
        axforge_api_key="k",
        llm_cache_dir=tmp_path / "c",
        llm_call_log=tmp_path / "l.jsonl",
    )
    c = Client()
    m = [{"role": "user", "content": "hi"}]
    gateway.chat(m, settings=s, client=c)
    gateway.chat(m, settings=s, client=c)  # served from the cache
    assert c.calls == 1 and axforge.totals()["requests"] == 1


def test_in_flight_requests_count_against_the_ceiling(ledger):
    ledger.write_text(_row(axforge.SAFETY_CEILING - 10_000) + "\n", encoding="utf-8")
    axforge.reserve(6_000)  # first parallel request fits
    try:
        with pytest.raises(axforge.AxForgeRefused, match="safety ceiling"):
            axforge.reserve(6_000)  # the second would cross it together with the first
    finally:
        axforge.release(6_000)
    axforge.reserve(6_000)  # released: fits again
    axforge.release(6_000)
    assert axforge._inflight == 0


def test_reservation_is_released_after_success_and_after_errors(ledger):
    c = Client()
    gateway._call_axforge(c, {"model": axforge.MODEL, "max_tokens": 500})
    err = RuntimeError("x")
    err.status_code = 503
    with pytest.raises(gateway.GatewayError):
        gateway._call_axforge(Client(err=err), {"model": axforge.MODEL, "max_tokens": 500})
    assert axforge._inflight == 0
