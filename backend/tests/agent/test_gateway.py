import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from traceforge.agent import gateway
from traceforge.agent.cache import cache_key
from traceforge.agent.gateway import GatewayError, chat
from traceforge.config import Settings

MSGS = [{"role": "user", "content": "hi"}]
SECRET = "sk-super-secret-123"


class HttpError(Exception):
    def __init__(self, status: int):
        self.status_code = status


class FakeClient:
    def __init__(self, fail_first: int = 0, status: int = 429):
        self.calls = 0
        self.fail_first, self.status = fail_first, status
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise HttpError(self.status)
        fn = SimpleNamespace(name="get_service_status", arguments='{"service":"worker"}')
        msg = SimpleNamespace(content=None, tool_calls=[SimpleNamespace(function=fn)])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=msg)],
            usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=500),
        )


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(gateway.time, "sleep", lambda _: None)


def settings(tmp_path, **kw) -> Settings:
    base = dict(
        _env_file=None,
        llm_cache_dir=tmp_path / "cache",
        llm_call_log=tmp_path / "calls.jsonl",
        llm_max_rps=1000,
        llm_prices={"qwen2.5-coder:7b": (1.0, 2.0)},
        openrouter_api_key=SecretStr(SECRET),
    )
    return Settings(**(base | kw))


def test_cache_miss_then_hit(tmp_path):
    s, c = settings(tmp_path), FakeClient()
    first = chat(MSGS, settings=s, client=c)
    second = chat(MSGS, settings=s, client=c)
    assert (first.cache_hit, second.cache_hit) == (False, True)
    assert c.calls == 1
    assert second.tool_calls[0].name == "get_service_status"


def test_no_cache_forces_live_call(tmp_path):
    s, c = settings(tmp_path), FakeClient()
    chat(MSGS, settings=s, client=c)
    chat(MSGS, settings=s, client=c, use_cache=False)
    assert c.calls == 2


def test_retry_on_429_then_success(tmp_path):
    c = FakeClient(fail_first=2)
    assert chat(MSGS, settings=settings(tmp_path), client=c).tool_calls
    assert c.calls == 3


def test_gateway_error_after_max_retries(tmp_path):
    c = FakeClient(fail_first=99, status=503)
    with pytest.raises(GatewayError):
        chat(MSGS, settings=settings(tmp_path), client=c)
    assert c.calls == gateway.MAX_RETRIES


def test_non_retryable_status_fails_fast(tmp_path):
    c = FakeClient(fail_first=99, status=400)
    with pytest.raises(GatewayError):
        chat(MSGS, settings=settings(tmp_path), client=c)
    assert c.calls == 1


def test_cost_calculation(tmp_path):
    r = chat(MSGS, settings=settings(tmp_path), client=FakeClient())
    assert r.list_price_usd == pytest.approx((1000 * 1.0 + 500 * 2.0) / 1e6)


def test_unknown_price_is_none(tmp_path):
    s = settings(tmp_path, llm_prices={})
    assert chat(MSGS, settings=s, client=FakeClient()).list_price_usd is None


def test_key_stable_across_dict_order():
    a = {"provider": "p", "model": "m", "messages": [{"role": "user", "content": "x"}]}
    b = {"messages": [{"content": "x", "role": "user"}], "model": "m", "provider": "p"}
    assert cache_key(a) == cache_key(b)


def test_replicate_index_changes_key(tmp_path):
    s, c = settings(tmp_path), FakeClient()
    chat(MSGS, settings=s, client=c, replicate_index=0)
    chat(MSGS, settings=s, client=c, replicate_index=1)
    assert c.calls == 2
    chat(MSGS, settings=s, client=c, replicate_index=1)
    assert c.calls == 2


@pytest.mark.parametrize(
    "kw",
    [
        {"llm_provider": "openrouter", "llm_model": "some/model"},
        {"llm_provider": "openrouter", "llm_model": "some/model:free-not"},
        {"llm_provider": "mistral", "llm_model": "devstral"},
        {"llm_provider": "groq", "llm_model": "llama"},
    ],
)
def test_free_only_guard_refuses(tmp_path, kw):
    c = FakeClient()
    with pytest.raises(GatewayError, match="free_only"):
        chat(MSGS, settings=settings(tmp_path, **kw), client=c)
    assert c.calls == 0


def test_free_only_allows_free_openrouter_and_explicit_allowlist(tmp_path):
    kw = {"llm_provider": "openrouter", "llm_model": "qwen/qwen3-coder:free"}
    assert chat(MSGS, settings=settings(tmp_path, **kw), client=FakeClient())
    kw = {"llm_provider": "mistral", "llm_free_allowlist": {"mistral"}}
    assert chat(MSGS, settings=settings(tmp_path, **kw), client=FakeClient())


def test_no_secret_or_content_in_logs(tmp_path):
    s = settings(tmp_path, llm_provider="openrouter", llm_model="a/b:free")
    msgs = [{"role": "user", "content": "private prompt text"}]
    chat(msgs, settings=s, client=FakeClient())
    chat(msgs, settings=s, client=FakeClient())
    with pytest.raises(GatewayError):
        chat(msgs, settings=s, client=FakeClient(fail_first=99, status=500), use_cache=False)
    log = s.llm_call_log.read_text("utf-8")
    assert len(log.splitlines()) == 3
    assert SECRET not in log and "private prompt text" not in log
    assert SECRET not in repr(s) and SECRET not in json.dumps(s.model_dump(mode="json"))


def test_prompt_too_long_raises_before_sending(tmp_path):
    c = FakeClient()
    with pytest.raises(GatewayError):
        chat(MSGS, settings=settings(tmp_path, llm_max_prompt_chars=3), client=c)
    assert c.calls == 0


TOOLS = [{"type": "function", "function": {"name": "get_service_status", "parameters": {}}}]


def test_tool_call_printed_as_json_text_is_accepted_only_for_offered_tools():
    ok = gateway.tool_calls_from_text(
        '{"name": "get_service_status", "arguments": {"service": "worker"}}', TOOLS
    )
    assert [(c.name, json.loads(c.arguments)) for c in ok] == [
        ("get_service_status", {"service": "worker"})
    ]
    assert gateway.tool_calls_from_text('{"name": "delete_all", "arguments": {}}', TOOLS) == []
    assert gateway.tool_calls_from_text("sure, calling it", TOOLS) == []
    assert gateway.tool_calls_from_text('{"name": "get_service_status"}', TOOLS) == []
    assert (
        gateway.tool_calls_from_text('{"name": "get_service_status", "arguments": {}}', None) == []
    )


@pytest.mark.parametrize(
    "model",
    ["devstral-small-2:24b-cloud", "zerocopia/devstral-small-2:24b-cloud", "gpt-oss:cloud"],
)
def test_ollama_cloud_models_refused_unless_explicitly_allowed(model):
    s = Settings(llm_provider="ollama", llm_model=model)
    with pytest.raises(GatewayError, match="Ollama cloud"):
        gateway.check_allowed(s)
    gateway.check_allowed(
        Settings(llm_provider="ollama", llm_model=model, llm_allow_ollama_cloud=True)
    )


def test_local_ollama_models_are_not_treated_as_cloud():
    for m in ("qwen2.5-coder:7b", "devstral-small-2:24b", "qwen2.5-coder-7b-ctx16k"):
        gateway.check_allowed(Settings(llm_provider="ollama", llm_model=m))


def test_attempt_index_makes_identical_prompts_distinct_requests(tmp_path):
    """A repair attempt after the first must not replay attempt 1 from the cache (F0 attempts are
    'fresh'); attempt 1 keeps its original cache key so legitimate cached results stay valid."""
    s, c = settings(tmp_path), FakeClient()
    chat(MSGS, settings=s, client=c)
    assert chat(MSGS, settings=s, client=c).cache_hit  # same attempt: still a hit
    second = chat(MSGS, settings=s, client=c, attempt_index=1)
    third = chat(MSGS, settings=s, client=c, attempt_index=2)
    assert not second.cache_hit and not third.cache_hit and c.calls == 3
    assert chat(MSGS, settings=s, client=c, attempt_index=1).cache_hit  # reruns of it are cached
    assert c.calls == 3


def test_attempt_index_is_not_sent_and_first_attempt_key_is_unchanged(tmp_path):
    seen = {}

    class Spy(FakeClient):
        def _create(self, **kw):
            seen.update(kw)
            return super()._create(**kw)

    s = settings(tmp_path)
    chat(MSGS, settings=s, client=Spy(), attempt_index=2)
    assert "attempt_index" not in seen and "replicate_index" not in seen
    legacy = {
        "provider": s.llm_provider, "model": s.llm_model, "messages": MSGS, "tools": None,
        "temperature": 0.0, "max_tokens": s.llm_max_output_tokens, "seed": 0, "replicate_index": 0,
    }  # fmt: skip
    from traceforge.agent import cache

    c = FakeClient()
    chat(MSGS, settings=s, client=c)
    assert cache.get(s.llm_cache_dir, s.llm_provider, s.llm_model, cache_key(legacy)) is not None


def test_replicates_are_independent_live_requests(tmp_path):
    s, c = settings(tmp_path), FakeClient()
    runs = [chat(MSGS, settings=s, client=c, replicate_index=r) for r in range(3)]
    assert [r.cache_hit for r in runs] == [False, False, False] and c.calls == 3
    assert chat(MSGS, settings=s, client=c, replicate_index=1).cache_hit  # a resume reuses its own


def test_requests_with_different_inputs_never_share_a_response(tmp_path):
    """Feedback-carrying and feedback-free prompts, or L and G contexts, are different keys."""
    s, c = settings(tmp_path), FakeClient()
    base = [{"role": "user", "content": "patch the file"}]
    with_fb = [
        {
            "role": "user",
            "content": "patch the file\n<visible_test_feedback>x</visible_test_feedback>",
        }
    ]
    other_ctx = [{"role": "user", "content": "patch the file (graph context)"}]
    for m in (base, with_fb, other_ctx):
        assert not chat(m, settings=s, client=c).cache_hit
    assert c.calls == 3 and chat(base, settings=s, client=c).cache_hit and c.calls == 3


class TruncClient(FakeClient):
    """Reply ends at the output cap with no content (hidden reasoning used the budget)."""

    def _create(self, **kw):
        self.calls += 1
        msg = SimpleNamespace(content="", tool_calls=[])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=msg, finish_reason="length")],
            usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=4096),
        )


def test_truncated_reply_is_not_cached_or_replayed(tmp_path):
    s, c = settings(tmp_path), TruncClient()
    a = chat(MSGS, settings=s, client=c)
    b = chat(MSGS, settings=s, client=c)
    assert (a.cache_hit, b.cache_hit, c.calls) == (False, False, 2)  # both are live requests
    assert a.finish_reason == "length"


def test_previously_cached_truncated_reply_is_a_miss(tmp_path):
    from traceforge.agent import cache

    s = settings(tmp_path)
    req = {
        "provider": s.llm_provider, "model": s.llm_model, "messages": MSGS, "tools": None,
        "temperature": 0.0, "max_tokens": s.llm_max_output_tokens, "seed": 0, "replicate_index": 0,
    }  # fmt: skip
    bad = gateway.ModelResponse(
        content="", tokens_in=1, tokens_out=4096, latency_ms=0.0, provider=s.llm_provider,
        model=s.llm_model, list_price_usd=0.0, finish_reason="length",
    )  # fmt: skip
    cache.put(
        s.llm_cache_dir, s.llm_provider, s.llm_model, cache.cache_key(req), req, bad.model_dump()
    )
    c = FakeClient()
    r = chat(MSGS, settings=s, client=c)
    assert r.cache_hit is False and c.calls == 1
