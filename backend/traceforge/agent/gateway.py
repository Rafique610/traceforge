"""One way to call any OpenAI-compatible chat provider: cached, rate-limited, logged."""

import json
import time
from typing import Any

import openai
from pydantic import BaseModel

from traceforge.agent import axforge, beatapi, cache
from traceforge.agent.call_log import log_call
from traceforge.config import Settings, get_settings

BASE_URLS = {
    "axforge": axforge.BASE_URL,
    "beatapi": beatapi.BASE_URL,
    "openrouter": "https://openrouter.ai/api/v1",
    "mistral": "https://api.mistral.ai/v1",
    "groq": "https://api.groq.com/openai/v1",
}
MAX_RETRIES = 5
_last_call = 0.0


class GatewayError(RuntimeError):
    """Call failed or was refused. Callers record INCONCLUSIVE/UNVERIFIED, never invent output."""


class OutputTruncated(GatewayError):
    """The reply hit the output-token cap (finish_reason 'length') and has no usable content.
    Reasoning models can spend the whole budget on hidden reasoning; raise llm_max_output_tokens."""


class ToolCall(BaseModel):
    name: str
    arguments: str  # raw JSON string


class ModelResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = []
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    cache_hit: bool = False
    provider: str
    model: str
    list_price_usd: float | None = None  # None when the model has no price entry
    finish_reason: str | None = None  # 'length' means the reply was truncated


def tool_calls_from_text(content: str | None, tools: list[dict] | None) -> list["ToolCall"]:
    """Some local models (qwen2.5-coder via Ollama) print the call as JSON text instead of
    `tool_calls`. Accept it only if it is exactly {name, arguments} for a tool we offered."""
    if not content or not tools:
        return []
    try:
        obj = json.loads(content.strip())
    except ValueError:
        return []
    names = {t["function"]["name"] for t in tools}
    if not (isinstance(obj, dict) and set(obj) == {"name", "arguments"} and obj["name"] in names):
        return []
    args = obj["arguments"]
    return [
        ToolCall(name=obj["name"], arguments=args if isinstance(args, str) else json.dumps(args))
    ]


def is_ollama_cloud(model: str) -> bool:
    """Cloud-tagged Ollama models (`...-cloud`, `...:cloud`) run on ollama.com, not locally."""
    tag = model.rsplit(":", 1)[-1].lower()
    return tag == "cloud" or tag.endswith("-cloud")


def check_allowed(s: Settings) -> None:
    if s.llm_provider == "axforge":  # not switchable: even with llm_free_only=false
        try:
            axforge.guard_model(s.llm_model)
        except axforge.AxForgeRefused as e:
            raise GatewayError(str(e)) from e
    if s.llm_provider == "beatapi":  # not switchable: even with llm_free_only=false
        try:
            beatapi.guard_model(s.llm_model)
        except beatapi.BeatApiRefused as e:
            raise GatewayError(str(e)) from e
    if not s.llm_free_only:
        return
    if s.llm_provider not in s.llm_free_allowlist:
        raise GatewayError(f"free_only: provider '{s.llm_provider}' is not allowlisted")
    if s.llm_provider == "openrouter" and not s.llm_model.endswith(":free"):
        raise GatewayError("free_only: openrouter model id must end with ':free'")
    if s.llm_provider == "ollama" and is_ollama_cloud(s.llm_model) and not s.llm_allow_ollama_cloud:
        raise GatewayError(
            "free_only: Ollama cloud models bill per token and have no confirmed free allowance; "
            "set TRACEFORGE_LLM_ALLOW_OLLAMA_CLOUD=true only after checking the account balance"
        )


def list_price(s: Settings, tokens_in: int, tokens_out: int) -> float | None:
    price = s.llm_prices.get(s.llm_model)
    return None if price is None else (tokens_in * price[0] + tokens_out * price[1]) / 1e6


def make_client(s: Settings) -> openai.OpenAI:
    if s.llm_provider == "ollama":
        return openai.OpenAI(base_url=s.ollama_base_url, api_key="ollama", max_retries=0)
    key = getattr(s, f"{s.llm_provider}_api_key").get_secret_value()
    return openai.OpenAI(base_url=BASE_URLS[s.llm_provider], api_key=key, max_retries=0)


def _throttle(max_rps: float) -> None:
    global _last_call
    wait = _last_call + 1 / max_rps - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _call_beatapi(client: Any, kwargs: dict[str, Any]) -> Any:
    """One attempt only: no retry, no model change, no fallback host. Errors stop the caller."""
    try:
        beatapi.guard_model(kwargs.get("model", ""))  # last line of defence before the network
    except beatapi.BeatApiRefused as e:
        raise GatewayError(str(e)) from e
    kwargs.pop("seed", None)  # not documented for this provider; temperature 0 is still sent
    beatapi.pace()
    try:
        return client.chat.completions.create(**kwargs)
    except openai.APIConnectionError as e:
        raise GatewayError("cannot reach beatapi") from e
    except Exception as e:
        status = getattr(e, "status_code", None)
        raise GatewayError(
            f"beatapi call failed ({status}): {type(e).__name__}; not retried"
        ) from e


def _call_axforge(client: Any, kwargs: dict[str, Any]) -> Any:
    """One attempt only: no retry, no model change, no fallback host. Errors stop the caller."""
    try:
        axforge.guard_model(kwargs.get("model", ""))
    except axforge.AxForgeRefused as e:
        raise GatewayError(str(e)) from e
    kwargs.pop("seed", None)
    try:
        return client.chat.completions.create(**kwargs)
    except openai.APIConnectionError as e:
        raise GatewayError("cannot reach axforge") from e
    except Exception as e:
        status = getattr(e, "status_code", None)
        raise GatewayError(
            f"axforge call failed ({status}): {type(e).__name__}; not retried"
        ) from e


def _call(client: Any, s: Settings, request: dict[str, Any]) -> Any:
    skip = ("provider", "replicate_index")
    kwargs = {k: v for k, v in request.items() if k not in skip and v is not None}
    if s.llm_provider == "axforge":
        return _call_axforge(client, kwargs)
    if s.llm_provider == "beatapi":
        return _call_beatapi(client, kwargs)
    for attempt in range(MAX_RETRIES):
        _throttle(s.llm_max_rps)
        try:
            return client.chat.completions.create(**kwargs)
        except openai.APIConnectionError as e:
            raise GatewayError(f"cannot reach {s.llm_provider} (is it running?)") from e
        except Exception as e:
            status = getattr(e, "status_code", None)
            if status is None or not (status == 429 or status >= 500):
                raise GatewayError(f"{s.llm_provider} call failed: {type(e).__name__}") from e
            if attempt == MAX_RETRIES - 1:
                raise GatewayError(
                    f"{s.llm_provider} failed after {MAX_RETRIES} tries ({status})"
                ) from e
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    *,
    settings: Settings | None = None,
    client: Any = None,
    use_cache: bool = True,
    max_tokens: int | None = None,
    temperature: float = 0.0,
    seed: int = 0,
    replicate_index: int = 0,
) -> ModelResponse:
    s = settings or get_settings()
    check_allowed(s)
    if sum(len(json.dumps(m)) for m in messages) > s.llm_max_prompt_chars:
        raise GatewayError("prompt exceeds llm_max_prompt_chars")
    request = {
        "provider": s.llm_provider,
        "model": s.llm_model,
        "messages": messages,
        "tools": tools,
        "temperature": temperature,
        "max_tokens": max_tokens or s.llm_max_output_tokens,
        "seed": seed,
        "replicate_index": replicate_index,
    }
    if s.llm_provider == "axforge" and s.llm_reasoning_effort:
        request["extra_body"] = {
            "reasoning_effort": s.llm_reasoning_effort
        }  # part of the cache key
    key = cache.cache_key(request)
    log = {
        "provider": s.llm_provider,
        "model": s.llm_model,
        "key": key,
        "n_messages": len(messages),
    }

    if use_cache and (hit := cache.get(s.llm_cache_dir, s.llm_provider, s.llm_model, key)):
        resp = ModelResponse(**{**hit, "cache_hit": True})
        log_call(
            s.llm_call_log,
            **log,
            ok=True,
            cache_hit=True,
            tokens_in=resp.tokens_in,
            tokens_out=resp.tokens_out,
            latency_ms=0.0,
            list_price_usd=resp.list_price_usd,
        )
        return resp

    t0 = time.monotonic()
    try:
        raw = _call(client or make_client(s), s, request)
    except GatewayError as e:
        log_call(s.llm_call_log, **log, ok=False, error=str(e))
        raise
    msg = raw.choices[0].message
    usage = raw.usage
    tin, tout = (usage.prompt_tokens, usage.completion_tokens) if usage else (0, 0)
    resp = ModelResponse(
        content=msg.content,
        tool_calls=[
            ToolCall(name=t.function.name, arguments=t.function.arguments)
            for t in (msg.tool_calls or [])
        ]
        or tool_calls_from_text(msg.content, tools),
        tokens_in=tin,
        tokens_out=tout,
        latency_ms=(time.monotonic() - t0) * 1000,
        provider=s.llm_provider,
        model=s.llm_model,
        list_price_usd=list_price(s, tin, tout),
        finish_reason=getattr(raw.choices[0], "finish_reason", None),
    )
    if use_cache:
        cache.put(s.llm_cache_dir, s.llm_provider, s.llm_model, key, request, resp.model_dump())
    log_call(
        s.llm_call_log,
        **log,
        ok=True,
        cache_hit=False,
        tokens_in=tin,
        tokens_out=tout,
        latency_ms=resp.latency_ms,
        list_price_usd=resp.list_price_usd,
    )
    return resp
