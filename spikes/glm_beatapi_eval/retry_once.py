"""ONE controlled retry of the first request that returned HTTP 503 upstream_timeout.

Authorised by Ruhan: exactly ONE additional live request with the ORIGINAL configuration
(max_tokens 6000, temperature 0, model glm-5.3-flash-free, same tool schemas and messages).
- The payload is rebuilt with the harness's own code and the gateway cache key is compared with the
  key of the failed request; if it differs, nothing is sent.
- $0 guards stay on: gateway beatapi profile (exact model id only, 65 s pacing, single attempt, no
  retry) and the read-only usage endpoint checked before and after.
- No second attempt: on any error the result is recorded and the script exits.
Run from backend/:  ..\\.venv.. python ..\\spikes\\glm_beatapi_eval\\retry_once.py [--check-only]
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import agent_loop  # noqa: E402
import run_eval  # noqa: E402
import usage_guard  # noqa: E402

from traceforge.agent import beatapi, cache, gateway  # noqa: E402
from traceforge.config import Settings  # noqa: E402

FAILED_KEY = "3c2d6194b13fe7552c2a47229f1c89cd908387883e321fef21cbfe57c64b082d"
FAILED_AT_UTC = datetime(2026, 11, 21, 23, 11, 33, tzinfo=timezone.utc)  # from the 503 request id
MIN_WAIT = timedelta(minutes=15)  # "a reasonable interval" before the retry


def build_request(settings: Settings) -> dict:
    task = run_eval.load_task("T1")
    messages = [
        {"role": "system", "content": agent_loop.SYSTEM.format(ask=task["ask"])},
        {"role": "user", "content": "BUG REPORT\n\n" + task["bug_report"]},
    ]
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "messages": messages,
        "tools": agent_loop.SCHEMAS,
        "temperature": 0.0,
        "max_tokens": run_eval.MAX_TOKENS,
        "seed": 0,
        "replicate_index": 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true")
    a = ap.parse_args()
    settings = Settings(
        llm_provider="beatapi",
        llm_model=run_eval.MODEL,
        llm_free_only=True,
        llm_cache_dir=run_eval.RESULTS / "cache",
        llm_call_log=run_eval.RESULTS / "llm_calls.jsonl",
    )
    assert settings.llm_model == beatapi.FREE_MODEL == "glm-5.3-flash-free"
    assert run_eval.MAX_TOKENS == 6000, "the retry must use the original 6000-token configuration"
    req = build_request(settings)
    key = cache.cache_key(req)
    same = key == FAILED_KEY
    print(f"payload fingerprint {key[:12]}... vs failed request {FAILED_KEY[:12]}...: identical={same}")
    print(f"model={req['model']} max_tokens={req['max_tokens']} temperature={req['temperature']} tools={len(req['tools'])}")
    if not same:
        sys.exit("payload differs from the failed request: nothing was sent")
    if a.check_only:
        print("check-only: nothing sent")
        return

    out: dict = {"authorised": "exactly one additional live request, original 6000-token config"}
    api_key = settings.beatapi_api_key.get_secret_value()
    before = usage_guard.fetch_usage(api_key)
    bd = before.get("data", {})
    out["usage_before"] = {k: bd.get(k) for k in ("credit_balance", "credits_settled", "total_tasks")}
    out["usage_before"]["models"] = [m["model"] for m in bd.get("by_model", [])]
    bad = usage_guard.violations(before)
    if bad:
        sys.exit(f"usage guard: {bad}; nothing sent")

    wait_s = (FAILED_AT_UTC + MIN_WAIT - datetime.now(timezone.utc)).total_seconds()
    out["waited_for_interval_s"] = max(0, round(wait_s))
    if wait_s > 0:
        print(f"waiting {wait_s:.0f}s so that >= 15 min have passed since the failure", flush=True)
        time.sleep(wait_s)

    out["sent_at_utc"] = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    try:
        r = gateway.chat(req["messages"], req["tools"], settings=settings, use_cache=True,
                         max_tokens=req["max_tokens"], temperature=0.0)
        out["result"] = "success"
        out["wall_s"] = round(time.monotonic() - t0, 2)
        out["response"] = {
            "model": r.model, "finish_reason": r.finish_reason, "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out, "latency_ms": round(r.latency_ms),
            "content_chars": len(r.content or ""), "content_head": (r.content or "")[:300],
            "tool_calls": [{"name": t.name, "arguments": t.arguments[:300]} for t in r.tool_calls],
        }
    except gateway.GatewayError as e:
        cause = e.__cause__
        hdr = getattr(getattr(cause, "response", None), "headers", None)
        out["result"] = "error"
        out["wall_s"] = round(time.monotonic() - t0, 2)
        out["status_code"] = getattr(cause, "status_code", None)
        out["error"] = str(e)
        out["body"] = str(getattr(cause, "body", ""))[:400]
        out["retry_after_header"] = None if hdr is None else hdr.get("retry-after")
    after = usage_guard.fetch_usage(api_key)
    ad = after.get("data", {})
    out["usage_after"] = {k: ad.get(k) for k in ("credit_balance", "credits_settled", "total_tasks")}
    out["usage_after"]["models"] = [m["model"] for m in ad.get("by_model", [])]
    out["usage_violations_after"] = usage_guard.violations(after)
    (run_eval.RESULTS / "retry_once.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
