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
    if s.llm_provider == "axforge":
        slot = axforge.require_slot(s.axforge_key_slot)  # slot 2 refused unless owner-enabled
        field = "axforge_api_key" if slot == "1" else "axforge_api_key2"
        key = getattr(s, field).get_secret_value()
        if not key and slot == "2":
            raise axforge.AxForgeRefused(f"axforge: no API key configured for slot {slot}")
        return openai.OpenAI(base_url=BASE_URLS["axforge"], api_key=key, max_retries=0)
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
    if (why := beatapi.halted()) is not None:  # the first failure ended BeatAPI use: no more calls
        raise GatewayError(f"beatapi halted after the first provider failure ({why}); not retried")
    beatapi.pace()
    try:  # streamed: a long silent reply was cut off by the provider (see beatapi.stream_kwargs)
        raw = client.chat.completions.create(**beatapi.stream_kwargs(kwargs))
        resp = beatapi.collect_stream(raw)
    except openai.APIConnectionError as e:
        beatapi.halt("cannot reach beatapi")
        beatapi.stamp_done()
        raise GatewayError("cannot reach beatapi") from e
    except Exception as e:
        status = getattr(e, "status_code", None)
        beatapi.halt(f"{status}: {type(e).__name__}")
        beatapi.stamp_done()
        raise GatewayError(
            f"beatapi call failed ({status}): {type(e).__name__}; not retried"
        ) from e
    beatapi.stamp_done()
    beatapi.record_usage(getattr(resp, "usage", None))
    return resp


def _call_axforge(client: Any, kwargs: dict[str, Any], slot: str = "1") -> Any:
    """One attempt only: no retry, no model change, no fallback host. Errors stop the caller.

    The persistent token ledger is checked before sending (80% safety ceiling, counting requests in
    flight) and updated after with the usage the provider reported."""
    if (why := axforge.halted(slot)) is not None:  # first failure ends use of this key slot
        raise GatewayError(f"axforge halted after the first provider failure ({why}); not retried")
    est_in = axforge.estimate_input_tokens(kwargs)
    reserved = est_in + int(kwargs.get("max_tokens") or 4096)  # worst case: input + full output
    try:
        axforge.guard_model(kwargs.get("model", ""))
        axforge.reserve(reserved, slot=slot)
    except axforge.AxForgeRefused as e:
        raise GatewayError(str(e)) from e
    try:
        axforge.pace(
            slot=slot
        )  # machine-wide: >= 30 s between request STARTS, one request in flight
    except axforge.AxForgeRateLimited as e:  # a Retry-After from an earlier 429 has not elapsed
        axforge.release(reserved, slot)
        raise GatewayError(str(e)) from e
    except BaseException:
        axforge.release(reserved, slot)
        raise
    try:
        if (why := axforge.halted(slot)) is not None:  # a failure happened while this call waited
            raise GatewayError(f"axforge halted after the first provider failure ({why})")
        kwargs.pop("seed", None)
        try:
            resp = client.chat.completions.create(**kwargs)
        except openai.APIConnectionError as e:
            axforge.record_error(
                None, estimated_tokens=est_in, slot=slot
            )  # may have reached the server
            axforge.halt("cannot reach axforge", slot)
            raise GatewayError("cannot reach axforge") from e
        except Exception as e:
            status = getattr(e, "status_code", None)
            maybe_processed = status is None or status >= 500
            axforge.halt(
                f"{status}: {type(e).__name__}", slot
            )  # the run stops at the first failure
            if status == 429:  # status, time, redacted headers and Retry-After are recorded
                info = axforge.record_429(e, slot=slot)
                raise GatewayError(
                    f"axforge call failed (429): {type(e).__name__}; not retried; "
                    f"retry_after={info['retry_after_s']}"
                ) from e
            axforge.record_error(
                status, estimated_tokens=est_in if maybe_processed else 0, slot=slot
            )
            raise GatewayError(
                f"axforge call failed ({status}): {type(e).__name__}; not retried"
            ) from e
        axforge.record(getattr(resp, "usage", None), slot=slot)
        return resp
    finally:
        axforge.done_turn(slot=slot)
        axforge.release(reserved, slot)


def _call(client: Any, s: Settings, request: dict[str, Any]) -> Any:
    skip = ("provider", "replicate_index", "attempt_index")
    kwargs = {k: v for k, v in request.items() if k not in skip and v is not None}
    if s.llm_provider == "axforge":
        return _call_axforge(client, kwargs, s.axforge_key_slot)
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


def reasoning_effort(s: Settings) -> str | None:
    """reasoning_effort to send, or None. AxForge: only when set. BeatAPI: 'low' unless set, because
    the free model's hidden reasoning filled the output cap and cut answers off (25 Nov: 10 of 30
    calls); a probe at 'low' answered shop_api-002 correctly in 247 tokens, 25 of them reasoning."""
    if s.llm_provider == "axforge":
        return s.llm_reasoning_effort
    if s.llm_provider == "beatapi":
        return s.llm_reasoning_effort or "low"
    return None


def _truncated(reply: dict) -> bool:
    """Output cap hit with no usable content (reasoning ate the budget): not cacheable."""
    return reply.get("finish_reason") == "length" and not (reply.get("content") or "").strip()


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
    attempt_index: int = 0,
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
    if attempt_index:  # part of the cache key only (never sent): a repair attempt after the first
        request["attempt_index"] = attempt_index  # is a new request even if its prompt is identical
    if effort := reasoning_effort(s):
        request["extra_body"] = {"reasoning_effort": effort}  # part of the cache key
    key = cache.cache_key(request)
    log = {
        "provider": s.llm_provider,
        "model": s.llm_model,
        "key": key,
        "n_messages": len(messages),
    }
    if s.llm_provider == "axforge":
        log["slot"] = s.axforge_key_slot  # the slot name only, never the key

    hit = cache.get(s.llm_cache_dir, s.llm_provider, s.llm_model, key) if use_cache else None
    if hit and _truncated(hit):
        hit = None  # a cached truncated reply is never replayed as if it were a fresh attempt
    if hit:
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
    if use_cache and not _truncated(resp.model_dump()):
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
