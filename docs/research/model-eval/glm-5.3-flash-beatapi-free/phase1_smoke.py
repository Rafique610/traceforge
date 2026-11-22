"""Phase 1 smoke test for BeatAPI `glm-5.3-flash-free` (ZERO-COST GUARDED).

Safety rules enforced in code:
- The model id is hard-coded to the exact free id; any other id (paid siblings such as
  glm-5.3-flash, glm-5.3, glm-5.3-flashx) is refused before any network call.
- The API key is read from the BEATAPI_API_KEY environment variable or the git-ignored .env
  at the repo root. It is never printed or written to the log.
- No retries. The fallback base URL is used ONLY if the first host is unreachable (connection
  error), never after an HTTP error.
- Any HTTP error stops the script and is logged verbatim. No other model is ever tried.
- Tests are spaced 65 s apart (free limit: 1 successful request per minute before first top-up).

Usage (from the repo root):  python docs/research/model-eval/glm-5.3-flash-beatapi-free/phase1_smoke.py [--tools] [--stream]
Default = ONE minimal request. --tools adds one tool-calling request, --stream one streaming request.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MODEL = "glm-5.3-flash-free"  # the ONLY id this script may send
BASES = ["https://direct.beatapi.io/v1", "https://api.beatapi.io/v1"]  # 2nd only if 1st unreachable
HERE = Path(__file__).parent
ROOT = HERE.parents[3]


def load_key() -> str:
    key = os.environ.get("BEATAPI_API_KEY", "")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_bytes().decode("utf-8-sig").splitlines():
            if line.startswith("BEATAPI_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("BEATAPI_API_KEY is not set (env var or .env). Nothing was sent.")
    return key


def post(base: str, key: str, body: dict, stream: bool = False):
    assert body.get("model") == MODEL, "refusing to send any model id other than " + MODEL
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        raw = resp.read().decode("utf-8", "ignore")
        return resp.status, raw, dict(resp.headers), time.time() - t0, None
    except urllib.error.HTTPError as e:  # HTTP error: report, do not retry, do not switch
        return e.code, e.read().decode("utf-8", "ignore"), dict(e.headers), time.time() - t0, None
    except (urllib.error.URLError, TimeoutError, OSError) as e:  # unreachable host
        return None, "", {}, time.time() - t0, repr(e)[:200]


def one(key: str, name: str, body: dict, log: list, stream: bool = False) -> bool:
    err = None
    for base in BASES:
        status, raw, headers, dt, err = post(base, key, body, stream)
        if err is None:
            break  # got an HTTP answer (success or error): never try the other host
    entry = {"test": name, "base": base, "http_status": status, "latency_s": round(dt, 2), "unreachable": err}
    keep = {k: v for k, v in headers.items() if k.lower() in ("retry-after", "x-request-id", "content-type")}
    entry["headers"] = keep
    if stream and status == 200:
        chunks = [l for l in raw.splitlines() if l.startswith("data:")]
        entry["stream_events"] = len(chunks)
        entry["stream_done_marker"] = any("[DONE]" in c for c in chunks)
        entry["stream_tail"] = chunks[-3:]
    else:
        try:
            j = json.loads(raw)
        except Exception:
            j = {"raw": raw[:400]}
        entry["response_model"] = j.get("model")
        entry["usage"] = j.get("usage")
        entry["error"] = j.get("error")
        ch = (j.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        entry["finish_reason"] = ch.get("finish_reason")
        entry["content"] = (msg.get("content") or "")[:400]
        entry["reasoning_present"] = bool(msg.get("reasoning") or msg.get("reasoning_content"))
        entry["tool_calls"] = msg.get("tool_calls")
        entry["cost_fields"] = {k: v for k, v in (j.get("usage") or {}).items() if "cost" in k.lower()}
    log.append(entry)
    print(json.dumps({k: entry[k] for k in ("test", "http_status", "latency_s", "response_model", "finish_reason") if k in entry}))
    return status == 200


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", action="store_true")
    ap.add_argument("--stream", action="store_true")
    a = ap.parse_args()
    key = load_key()
    log: list = []
    base_body = {"model": MODEL, "temperature": 0, "max_tokens": 512}
    ok = one(key, "minimal_chat", {**base_body, "messages": [{"role": "user", "content": "Reply with the single word: ok"}]}, log)
    if ok and a.tools:
        time.sleep(65)
        tools = [{"type": "function", "function": {"name": "get_service_status", "description": "Get status of a service", "parameters": {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"]}}}]
        ok = one(key, "tool_call", {**base_body, "messages": [{"role": "user", "content": "Check the status of service worker using the tool."}], "tools": tools}, log)
    if ok and a.stream:
        time.sleep(65)
        ok = one(key, "stream", {**base_body, "stream": True, "messages": [{"role": "user", "content": "Count from 1 to 3."}]}, log, stream=True)
    out = {"time_utc": datetime.now(timezone.utc).isoformat(), "model": MODEL, "results": log, "stopped_early": not ok}
    (HERE / "phase1_log.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("log written to phase1_log.json (no key recorded)")


if __name__ == "__main__":
    main()
