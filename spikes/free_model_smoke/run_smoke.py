"""Free-model smoke test: 8 fixed TraceForge-style debugging tasks through the REAL diagnose and
patch stages and the EXISTING gateway (cached, :free guard, temperature 0).

Run from backend/ with the project venv (see README.md):
    python ../spikes/free_model_smoke/run_smoke.py --provider ollama --model qwen2.5-coder-7b-ctx16k
    python ../spikes/free_model_smoke/run_smoke.py --provider openrouter --model "<id>:free" --max-requests 45

Spike code: never imported by backend/. Model calls happen ONLY in main() via gateway.chat.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from traceforge.agent import cache, gateway, prompting
from traceforge.agent import patch as patch_stage
from traceforge.agent.diagnose import Usage, diagnose
from traceforge.agent.gateway import ModelResponse
from traceforge.config import Settings

import report
import scoring
from smoke_tasks import REPAIRABLE, Task, build_tool_context, load_tasks

RESULTS = HERE / "results"
ChatImpl = Callable[[list, "list | None"], ModelResponse]


class RequestCapReached(Exception):
    """--max-requests reached; deliberately NOT a GatewayError so diagnose() cannot swallow it."""


class Budget:
    def __init__(self, cap: int) -> None:
        self.cap, self.live = cap, 0

    def exhausted(self) -> bool:
        return bool(self.cap) and self.live >= self.cap


class GatewayChat:
    """gateway.chat bound to (settings, replicate k). Cache hits are free and never capped."""

    def __init__(
        self, s: Settings, client: Any, k: int, budget: Budget, chat_fn=gateway.chat
    ):
        self.s, self.client, self.k, self.budget, self.chat_fn = (
            s,
            client,
            k,
            budget,
            chat_fn,
        )

    def _cached(self, messages: list, tools: list | None) -> bool:
        s = self.s
        req = {
            "provider": s.llm_provider,
            "model": s.llm_model,
            "messages": messages,
            "tools": tools,
            "temperature": 0.0,
            "max_tokens": s.llm_max_output_tokens,
            "seed": 0,
            "replicate_index": self.k,
        }  # mirrors gateway.chat's request dict, only to peek the cache
        key = cache.cache_key(req)
        return cache.get(s.llm_cache_dir, s.llm_provider, s.llm_model, key) is not None

    def __call__(self, messages: list, tools: list | None = None) -> ModelResponse:
        if not self._cached(messages, tools):
            if self.budget.exhausted():
                raise RequestCapReached
            self.budget.live += 1  # counts attempts: failed calls also burn free quota
        return self.chat_fn(
            messages,
            tools,
            settings=self.s,
            client=self.client,
            use_cache=True,
            temperature=0.0,
            seed=0,
            replicate_index=self.k,
        )


class Recorder:
    """Wraps any chat impl; keeps raw replies and every tool call the model emitted."""

    def __init__(self, impl: ChatImpl) -> None:
        self.impl, self.replies, self.calls, self.truncated = impl, [], [], False

    def __call__(self, messages: list, tools: list | None = None) -> ModelResponse:
        r = self.impl(messages, tools)
        self.replies.append(
            {
                "content": r.content,
                "tool_calls": [t.model_dump() for t in r.tool_calls],
                "finish_reason": r.finish_reason,
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "latency_ms": r.latency_ms,
                "cache_hit": r.cache_hit,
            }
        )
        self.calls += [(t.name, t.arguments) for t in r.tool_calls]
        self.truncated |= r.finish_reason == "length"
        return r


def run_task(task: Task, chat_impl: ChatImpl, k: int) -> dict[str, Any]:
    """One diagnose (+ one patch when the diagnosis is repairable), scored. Returns {record, raw}."""
    tc, bundle = build_tool_context(task)
    rec, usage = Recorder(chat_impl), Usage()
    result = diagnose(tc, bundle, rec, usage, prompting.DEFAULT_CONTEXT_BUDGET_CHARS)
    reply = failure = patch = None
    if result.submitted and result.diagnosis.cause_class in REPAIRABLE:
        n = len(rec.replies)
        _, _, failure = patch_stage.request_patch(tc, result.submitted, rec, usage)
        reply = rec.replies[-1]["content"] if len(rec.replies) > n else None
        patch = scoring.evaluate_patch(task, reply)
    record = scoring.score_run(
        task, result, rec.calls, reply, failure, patch, rec.truncated
    )
    record.update(
        k=k,
        n_requests=len(rec.replies),
        tokens_in=usage.tokens_in,
        tokens_out=usage.tokens_out,
        latency_ms=usage.latency_ms,
        cache_hits=usage.cache_hits,
        infra_failure=bool(
            result.failure_reason and result.failure_reason.startswith("provider_error")
        )
        or bool(failure and failure.startswith("provider_error")),
    )
    return {
        "record": record,
        "raw": {"replies": rec.replies, "patch_reply": reply, "trace": result.trace},
    }


def model_dir(base: Path, provider: str, model: str) -> Path:
    return base / re.sub(r"[^A-Za-z0-9._-]+", "_", f"{provider}__{model}")


def execute(
    tasks: list[Task],
    make_chat: Callable[[int], ChatImpl],
    out: Path,
    k_runs: int,
    force: bool = False,
) -> tuple[list[dict[str, Any]], bool]:
    """All runs, replicate-major (a full k=0 pass before k=1). Resumes from out/raw/*.json.
    Returns (records, incomplete)."""
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for k in range(k_runs):
        chat_impl = make_chat(k)
        for task in tasks:
            f = raw_dir / f"{task.id}__k{k}.json"
            if f.exists() and not force:
                saved = json.loads(f.read_text("utf-8"))["record"]
                if not saved["infra_failure"]:
                    records.append(saved)
                    print(f"[resume] {task.id} k={k}")
                    continue
            t0 = time.monotonic()
            try:
                run = run_task(task, chat_impl, k)
            except RequestCapReached:
                print(
                    f"[cap] --max-requests reached before {task.id} k={k}; rerun to resume"
                )
                return records, True
            f.write_text(json.dumps(run, indent=1), "utf-8")
            r = run["record"]
            print(
                f"[{task.id} k={k}] class={r['pred_class']} target_ok={r['target_ok']} "
                f"req={r['n_requests']} {time.monotonic() - t0:.0f}s"
            )
            records.append(r)
    return records, False


def write_results(
    records: list[dict[str, Any]], meta: dict[str, Any], out: Path
) -> None:
    agg = report.aggregate(records, meta)
    (out / "results.json").write_text(json.dumps(agg, indent=1), "utf-8")
    (out / "summary.md").write_text(report.to_markdown(agg), "utf-8")


def estimate(tasks: list[Task], k: int) -> str:
    rep = sum(t.repairable for t in tasks)
    lo, hi = (len(tasks) + rep) * k, (len(tasks) * 6 + rep) * k
    return f"{lo}..{hi} live requests (typical about {round(lo * 1.6)}); cache hits are free"


def build_settings(args: argparse.Namespace) -> Settings:
    s = Settings(
        llm_provider=args.provider,
        llm_model=args.model,
        llm_cache_dir=HERE / ".cache" / "llm",
        llm_call_log=RESULTS / "llm_calls.jsonl",
        llm_max_rps=args.max_rps,
        llm_max_output_tokens=args.max_output_tokens,
        ollama_base_url=args.ollama_url,
    )
    gateway.check_allowed(s)  # the free-only guard; never overridden here
    return s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provider", required=True, choices=["ollama", "openrouter"])
    ap.add_argument("--model", required=True)
    ap.add_argument(
        "--k", type=int, default=2, help="runs per task (replicate_index 0..k-1)"
    )
    ap.add_argument("--tasks", nargs="*", help="task ids (default all)")
    ap.add_argument(
        "--max-requests",
        type=int,
        default=45,
        help="live (uncached) requests cap; 0 = none",
    )
    ap.add_argument("--max-rps", type=float, default=0.3)
    ap.add_argument("--max-output-tokens", type=int, default=4096)
    ap.add_argument("--ollama-url", default="http://localhost:11434/v1")
    ap.add_argument("--timeout", type=float, default=900.0, help="per-request seconds")
    ap.add_argument("--out", type=Path, default=RESULTS)
    ap.add_argument(
        "--force",
        action="store_true",
        help="ignore saved run files (gateway cache still used)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="list tasks and estimate; no model calls"
    )
    args = ap.parse_args(argv)
    tasks = load_tasks(args.tasks)
    s = build_settings(args)
    print(f"{len(tasks)} tasks x K={args.k}: {estimate(tasks, args.k)}")
    if args.dry_run:
        return 0
    out = model_dir(args.out, args.provider, args.model)
    budget = Budget(args.max_requests)
    client = gateway.make_client(s).with_options(timeout=args.timeout)
    records, incomplete = execute(
        tasks, lambda k: GatewayChat(s, client, k, budget), out, args.k, args.force
    )
    meta = {
        "provider": args.provider,
        "model": args.model,
        "k": args.k,
        "max_requests": args.max_requests,
        "live_requests": budget.live,
        "incomplete": incomplete,
        "n_tasks": len(tasks),
    }
    write_results(records, meta, out)
    print(
        f"wrote {out / 'summary.md'} (live requests: {budget.live}, incomplete: {incomplete})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
