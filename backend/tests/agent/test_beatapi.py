"""BeatAPI free-only profile: only `glm-5.3-flash-free` can ever be sent; pacing; no retries."""

import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from traceforge.agent import beatapi, gateway
from traceforge.agent.gateway import GatewayError, chat
from traceforge.config import Settings

PAID_AND_LOOKALIKES = [
    "glm-5.3-flash",
    "glm-5.3",
    "glm-5.3-flashx",
    "glm-5.3-flash-free ",
    " glm-5.3-flash-free",
    "GLM-5.3-FLASH-FREE",
    "glm-5.3-flash-free2",
    "glm-5.3-flash-free:paid",
    "deepseek-v4.1-flash-free",
    "claude-sonnet-5-5",
    "",
]


class FakeClient:
    """Test double standing in for the OpenAI client; records every request it receives."""

    def __init__(self, fail_status: int | None = None):
        self.calls: list[dict] = []
        self.fail_status = fail_status
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        if self.fail_status:
            e = RuntimeError("boom")
            e.status_code = self.fail_status
            raise e
        msg = SimpleNamespace(content="ok", tool_calls=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=msg, finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
        )


@pytest.fixture(autouse=True)
def _isolate_ledger(monkeypatch, tmp_path):
    monkeypatch.setattr(beatapi, "LEDGER", tmp_path / "beatapi_usage.jsonl")
    beatapi.reset_halt()
    yield
    beatapi.reset_halt()


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Point pacing state and the call log/cache at tmp paths; never really sleep."""
    monkeypatch.setattr(beatapi, "STATE_FILE", tmp_path / "state.json")
    sleeps: list[float] = []
    monkeypatch.setattr(beatapi.time, "sleep", lambda s: sleeps.append(s))
    return tmp_path, sleeps


def settings(tmp_path, model="glm-5.3-flash-free", **kw):
    return Settings(
        llm_provider="beatapi",
        llm_model=model,
        beatapi_api_key=SecretStr("sk-test-secret-value"),
        llm_cache_dir=tmp_path / "cache",
        llm_call_log=tmp_path / "calls.jsonl",
        **kw,
    )


@pytest.mark.parametrize("model", PAID_AND_LOOKALIKES)
@pytest.mark.parametrize("free_only", [True, False])
def test_any_other_model_is_refused_before_the_network(isolated, model, free_only):
    tmp, _ = isolated
    client = FakeClient()
    with pytest.raises(GatewayError, match="only the exact model id"):
        chat(
            [{"role": "user", "content": "x"}],
            settings=settings(tmp, model, llm_free_only=free_only),
            client=client,
        )
    assert client.calls == []  # nothing was sent


def test_exact_free_model_is_sent_once_with_exact_id(isolated):
    tmp, sleeps = isolated
    client = FakeClient()
    r = chat(
        [{"role": "user", "content": "x"}], settings=settings(tmp), client=client, use_cache=False
    )
    assert r.content == "ok" and len(client.calls) == 1
    assert client.calls[0]["model"] == "glm-5.3-flash-free"
    assert "seed" not in client.calls[0]
    assert sleeps == []  # first request: no wait


def test_last_line_of_defence_blocks_a_tampered_request(isolated):
    """Even if something bypassed chat(), _call refuses a different model id."""
    tmp, _ = isolated
    client = FakeClient()
    with pytest.raises(GatewayError, match="only the exact model id"):
        gateway._call(client, settings(tmp), {"model": "glm-5.3-flash", "messages": []})
    assert client.calls == []


def test_pacing_waits_90s_between_live_requests(isolated, monkeypatch):
    tmp, sleeps = isolated
    clock = {"t": 1000.0}
    monkeypatch.setattr(beatapi.time, "time", lambda: clock["t"])
    client = FakeClient()
    s = settings(tmp)
    chat([{"role": "user", "content": "a"}], settings=s, client=client, use_cache=False)
    clock["t"] += 20.0  # only 20 s later
    chat([{"role": "user", "content": "b"}], settings=s, client=client, use_cache=False)
    assert len(client.calls) == 2
    assert sleeps and abs(sleeps[0] - 70.0) < 1e-6  # 90 - 20
    state = json.loads((tmp / "state.json").read_text())
    assert state["sent_at"] == 1020.0  # stamped when the second request was sent


def test_cache_hits_do_not_consume_the_minute(isolated):
    tmp, sleeps = isolated
    client = FakeClient()
    s = settings(tmp)
    msgs = [{"role": "user", "content": "same"}]
    chat(msgs, settings=s, client=client)
    chat(msgs, settings=s, client=client)  # served from cache
    assert len(client.calls) == 1 and sleeps == []


@pytest.mark.parametrize("status", [429, 500, 402, 404])
def test_errors_stop_immediately_without_retry_or_fallback(isolated, status):
    tmp, _ = isolated
    client = FakeClient(fail_status=status)
    with pytest.raises(GatewayError, match="not retried"):
        chat(
            [{"role": "user", "content": "x"}],
            settings=settings(tmp),
            client=client,
            use_cache=False,
        )
    assert len(client.calls) == 1  # exactly one attempt, no retry, no other model


def test_secret_never_appears_in_logs_or_repr(isolated):
    tmp, _ = isolated
    s = settings(tmp)
    chat([{"role": "user", "content": "x"}], settings=s, client=FakeClient(), use_cache=False)
    log = (tmp / "calls.jsonl").read_text()
    assert "sk-test-secret-value" not in log and "sk-test-secret-value" not in repr(s)


def test_base_url_is_fixed_and_key_alias_works(monkeypatch):
    assert gateway.BASE_URLS["beatapi"] == "https://direct.beatapi.io/v1"
    monkeypatch.setenv("BEATAPI_API_KEY", "sk-from-plain-name")
    assert (
        Settings(llm_provider="beatapi").beatapi_api_key.get_secret_value() == "sk-from-plain-name"
    )


def test_window_counts_from_completion_not_only_from_send(tmp_path):
    state = tmp_path / "s.json"
    t = {"now": 1000.0}
    beatapi.pace(sleep=lambda s: None, now=lambda: t["now"], state_file=state)  # sent at 1000
    t["now"] = 1040.0  # generation took 40 s
    beatapi.stamp_done(now=lambda: t["now"], state_file=state)
    t["now"] = 1066.0  # 66 s after send but only 26 s after completion
    assert beatapi.seconds_until_allowed(1066.0, state) == pytest.approx(64.0)
    assert beatapi.seconds_until_allowed(1131.0, state) == 0.0


def test_usage_is_recorded_in_a_development_ledger():
    from types import SimpleNamespace as N

    beatapi.record_usage(N(prompt_tokens=10, completion_tokens=4))
    beatapi.record_usage(None)
    rows = [json.loads(x) for x in beatapi.LEDGER.read_text("utf-8").splitlines()]
    assert rows[0]["tier"] == "development" and rows[0]["input_tokens"] == 10
    assert rows[1]["usage_source"] == "unknown"


def _chunk(content=None, tool=None, finish=None, usage=None):
    tcs = None
    if tool:
        idx, name, args = tool
        tcs = [SimpleNamespace(index=idx, function=SimpleNamespace(name=name, arguments=args))]
    delta = SimpleNamespace(content=content, tool_calls=tcs)
    choices = [SimpleNamespace(delta=delta, finish_reason=finish)] if usage is None else []
    return SimpleNamespace(choices=choices, usage=usage)


class StreamClient(FakeClient):
    """Returns the reply as stream chunks: text, then one tool call split over three pieces."""

    def _create(self, **kw):
        self.calls.append(kw)
        return iter(
            [
                _chunk(content="Looking at "),
                _chunk(content="schemas."),
                _chunk(tool=(0, "read_symbol", '{"path": "a.py",')),
                _chunk(tool=(0, None, ' "qualname": ')),
                _chunk(tool=(0, None, '"Order"}'), finish="tool_calls"),
                _chunk(usage=SimpleNamespace(prompt_tokens=70, completion_tokens=9)),
            ]
        )


def test_beatapi_requests_are_streamed_and_capped(isolated):
    tmp, _ = isolated
    client = StreamClient()
    tools = [{"type": "function", "function": {"name": "read_symbol", "parameters": {}}}]
    r = chat([{"role": "user", "content": "x"}], tools, settings=settings(tmp), client=client,
             use_cache=False, max_tokens=9000)  # fmt: skip
    sent = client.calls[0]
    assert sent["stream"] is True and sent["stream_options"] == {"include_usage": True}
    assert sent["max_tokens"] == beatapi.STREAM_MAX_TOKENS  # a larger request is capped
    assert r.content == "Looking at schemas." and r.finish_reason == "tool_calls"
    assert [(t.name, json.loads(t.arguments)) for t in r.tool_calls] == [
        ("read_symbol", {"path": "a.py", "qualname": "Order"})
    ]
    assert (r.tokens_in, r.tokens_out) == (70, 9)


def test_collect_stream_passes_a_non_streamed_reply_through():
    done = SimpleNamespace(choices=[], usage=None)
    assert beatapi.collect_stream(done) is done
