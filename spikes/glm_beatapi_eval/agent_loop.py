"""Tool-using agent loop: identical prompt, tools and budget for every task (<=14 model requests).

`chat_fn(messages, tools) -> ModelResponse` is injected (the real one wraps gateway.chat; unit
tests pass a scripted test double). Any GatewayError stops the whole evaluation: no retry."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from typing import Any

from tools import SCHEMAS, Toolbox

MAX_REQUESTS = 14
SYSTEM = """You are a software engineer working on a Python backend (package `traceforge`) in a \
sandboxed working copy. You are given a bug report. You have NO git access and no internet.

Tools: list_dir, read_file, grep, apply_edit, run_tests, submit_final. Paths are relative to the \
repository root; only `backend/traceforge` (source) and `backend/tests` (tests) exist for you.

Your job: (1) find the ROOT CAUSE of the reported bug in the source, (2) fix it with apply_edit \
(the smallest correct change; the fix may need several files), (3) verify with run_tests and do \
not break other tests, (4) call submit_final(diagnosis, root_cause_file, summary) exactly once \
when finished. `diagnosis` must name the file, function and mechanism of the root cause; \
`root_cause_file` is the main file; `summary` lists what you changed.

Budget: at most %d model requests in total. Each reply should contain tool calls; you may call \
several tools in one reply. Do not waste requests: read what you need, edit, run tests, then \
submit. If you are told this is your final request, call submit_final immediately. Respond with \
tool calls, not long prose. Note: the test sandbox has no git binary and no lab data files, so a few tests (those that \
create git repos or read lab manifests, mainly in tests/agent/test_repair_run.py and \
test_real_sources.py) fail in the sandbox regardless of your change; ignore those. \
Task type for this run: {ask}.""" % MAX_REQUESTS

ChatFn = Callable[[list[dict[str, Any]], list[dict[str, Any]]], Any]


class StopRun(RuntimeError):
    """Stop the whole evaluation (API error / usage anomaly / cap). `reason` is recorded."""


class LiveCounter:
    def __init__(self, cap: int = 60, start: int = 0):
        self.live, self.cap = start, cap


def _trim(s: str | None, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + f"...[+{len(s) - n} chars]"


def run_agent(task: dict, toolbox: Toolbox, chat_fn: ChatFn, *, max_requests: int = MAX_REQUESTS,
              guard=None, counter: LiveCounter | None = None, save: Callable[[dict], None] | None = None,
              gateway_error: type[BaseException] = RuntimeError) -> dict:
    counter = counter or LiveCounter()
    rec: dict[str, Any] = {"task": task["id"], "steps": [], "requests": 0, "live_requests": 0,
                           "submitted": None, "error": None, "stats": Counter()}
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM.format(ask=task["ask"])},
        {"role": "user", "content": "BUG REPORT\n\n" + task["bug_report"]},
    ]
    seen: Counter = Counter()
    stats = rec["stats"]
    for n in range(1, max_requests + 1):
        if counter.live >= counter.cap:
            rec["error"] = f"global live-request cap {counter.cap} reached"
            _finish(rec, save)
            raise StopRun(rec["error"])
        try:
            resp = chat_fn(messages, SCHEMAS)
        except gateway_error as e:
            rec["error"] = f"{type(e).__name__}: {e}"
            _finish(rec, save)
            raise StopRun(f"model endpoint error at request {n}: {e}") from e
        rec["requests"] = n
        if not resp.cache_hit:
            rec["live_requests"] += 1
            counter.live += 1
        step: dict[str, Any] = {
            "n": n, "latency_ms": round(resp.latency_ms), "tokens_in": resp.tokens_in,
            "tokens_out": resp.tokens_out, "finish_reason": resp.finish_reason,
            "cache_hit": resp.cache_hit, "content": _trim(resp.content, 2000), "calls": []}
        rec["steps"].append(step)
        if resp.finish_reason == "length":
            stats["finish_length"] += 1
        calls = resp.tool_calls
        asst: dict[str, Any] = {"role": "assistant", "content": resp.content or ""}
        if calls:
            asst["tool_calls"] = [
                {"id": f"call_{n}_{i}", "type": "function",
                 "function": {"name": c.name, "arguments": c.arguments}}
                for i, c in enumerate(calls)]
        messages.append(asst)
        if not calls:
            stats["no_tool_call_turns"] += 1
            messages.append({"role": "user", "content": "Respond with a tool call. Call "
                             "submit_final when done."})
        done = False
        for i, c in enumerate(calls):
            if done:
                break
            key = (c.name, c.arguments)
            seen[key] += 1
            if seen[key] == 3:
                stats["repeated_identical_call_loops"] += 1
            stats["tool_calls"] += 1
            if c.name == "submit_final":
                cat, text, done = _submit(c.arguments, rec)
            else:
                cat, text = toolbox.dispatch(c.name, c.arguments)
            if cat != "ok":
                stats[f"tool_{cat}"] += 1
            step["calls"].append({"name": c.name, "args": _trim(c.arguments, 1500),
                                  "category": cat, "result": _trim(text, 1200)})
            suffix = f"\n[requests used {n}/{max_requests}]"
            if n == max_requests - 1:
                suffix += " NEXT REQUEST IS YOUR LAST: call submit_final now."
            messages.append({"role": "tool", "tool_call_id": f"call_{n}_{i}",
                             "content": text + suffix})
        _snapshot(rec, save)
        if not resp.cache_hit and counter.live % 5 == 0 and guard:
            guard.check(f"{task['id']} after live request {counter.live}")
        if done:
            break
    if rec["submitted"] is None:
        rec["stats"]["no_submit"] = 1
    _finish(rec, save)
    return rec


def _submit(raw: str, rec: dict) -> tuple[str, str, bool]:
    try:
        a = json.loads(raw)
        vals = {k: a[k] for k in ("diagnosis", "root_cause_file", "summary")}
        if not all(isinstance(v, str) and v.strip() for v in vals.values()):
            raise ValueError("all three fields must be non-empty strings")
    except (ValueError, KeyError, TypeError) as e:
        return "bad_args", f"ERROR: submit_final needs diagnosis, root_cause_file, summary: {e}", False
    rec["submitted"] = vals
    return "ok", "submitted", True


def _snapshot(rec: dict, save) -> None:
    if save:
        save({**rec, "stats": dict(rec["stats"]), "partial": True})


def _finish(rec: dict, save) -> None:
    rec["stats"] = dict(rec["stats"])
    if save:
        save(rec)
