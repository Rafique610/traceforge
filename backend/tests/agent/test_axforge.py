import pytest

from traceforge.agent import axforge, gateway
from traceforge.config import Settings


def _s(model: str = "glm-5.3-flash", **kw) -> Settings:
    return Settings(llm_provider="axforge", llm_model=model, axforge_api_key="k", **kw)


def test_base_url_and_model_fixed():
    assert axforge.BASE_URL == "https://api.axforge.ai/v1"
    assert gateway.BASE_URLS["axforge"] == axforge.BASE_URL
    assert axforge.MODEL == "glm-5.3-flash"


@pytest.mark.parametrize(
    "bad", ["glm-5-3-flash", "GLM-5.3-flash", "glm-5.3-flash ", "qwen3.8-27b", "glm-5.3-flashx"]
)
@pytest.mark.parametrize("free_only", [True, False])
def test_other_ids_refused(bad, free_only):
    with pytest.raises(gateway.GatewayError):
        gateway.check_allowed(_s(bad, llm_free_only=free_only))


def test_exact_id_allowed():
    gateway.check_allowed(_s())


def test_call_single_attempt_no_seed_and_no_retry():
    calls = []

    class C:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    calls.append(kw)
                    e = RuntimeError("boom")
                    e.status_code = 402
                    raise e

    with pytest.raises(gateway.GatewayError, match="402.*not retried"):
        gateway._call_axforge(C, {"model": "glm-5.3-flash", "seed": 0, "max_tokens": 8})
    assert len(calls) == 1 and "seed" not in calls[0]


def test_tampered_model_blocked_before_network():
    with pytest.raises(gateway.GatewayError):
        gateway._call_axforge(object(), {"model": "qwen3.8-27b"})


def test_key_not_in_repr():
    assert "k" != repr(_s().axforge_api_key) and "'k'" not in repr(_s())


def test_reasoning_effort_sent_only_for_axforge_and_in_cache_key(tmp_path):
    seen = []

    class C:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    from types import SimpleNamespace as N

                    seen.append(kw)
                    m = N(content="OK", tool_calls=None)
                    return N(
                        choices=[N(message=m, finish_reason="stop")],
                        usage=N(prompt_tokens=1, completion_tokens=1),
                    )

    base = {"llm_cache_dir": tmp_path / "c", "llm_call_log": tmp_path / "l.jsonl"}
    msgs = [{"role": "user", "content": "x"}]
    gateway.chat(msgs, settings=_s(llm_reasoning_effort="low", **base), client=C)
    gateway.chat(msgs, settings=_s(**base), client=C)  # no effort: different cache key, second call
    assert seen[0]["extra_body"] == {"reasoning_effort": "low"} and "extra_body" not in seen[1]
