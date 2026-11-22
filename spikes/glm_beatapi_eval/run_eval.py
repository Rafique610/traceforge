"""Real smoke evaluation of glm-5.3-flash-free on 4 historical TraceForge bugs.

Run from D:\\TraceForge\\repo\\backend with the venv python:
  python ../spikes/glm_beatapi_eval/run_eval.py [--baseline-only] [--tasks T1,T2] [--cap 60]
Strictly sequential, one process. STOPS on any endpoint error or usage anomaly (no retry)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import agent_loop  # noqa: E402
import scoring  # noqa: E402
import tools  # noqa: E402
import usage_guard  # noqa: E402
import worktree  # noqa: E402

RESULTS = HERE / "results"
MODEL = "glm-5.3-flash-free"
MAX_TOKENS = 6000  # reasoning model: hidden reasoning shares this budget (must be >= 2000)


def load_task(tid: str) -> dict:
    return json.loads((HERE / "tasks" / f"{tid}.json").read_text(encoding="utf-8"))


def jwrite(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")


def baseline(task: dict, run=None) -> dict:
    """Prove the harness: buggy tree FAILS the hidden test, fixed reference tree passes it."""
    import sandbox_exec

    run = run or sandbox_exec.run_pytest
    tid = task["id"]
    out: dict = {"task": tid, "hidden": scoring.hidden_names(task)}
    gws = {}
    for label, buggy in (("buggy", True), ("fixed", False)):
        tree, hidden = worktree.build_visible(task, f"{tid}_{label}_base", buggy=buggy)
        try:
            if task["id"] == "T4":
                gws[label] = (tree / "backend/traceforge/agent/gateway.py").read_bytes().decode()
            sc = worktree.scorer_copy(tree, hidden, f"{tid}_{label}_base")
            try:
                r = run(sc, task["package_tests"], 300, 2500)
            finally:
                worktree.remove_scorer(sc)
        finally:
            worktree.cleanup(tree)
        res = {n: o for n, o in r["tests"]}
        out[label] = {"passed": r["passed"], "failed": r["failed"], "error": r["error"],
                      "hidden": {n: res.get(n, "missing") for n in out["hidden"]},
                      "failing": sorted(n for n, o in res.items() if o != "passed")}
        out[f"{label}_passing"] = sorted(n for n, o in res.items() if o == "passed")
    hb, hf = out["buggy"]["hidden"], out["fixed"]["hidden"]
    # the fixed reference may keep environment-only failures (no git / lab data in the image);
    # they are recorded in out["fixed"]["failing"] and excluded from regression scoring.
    out["reproduces"] = any(v != "passed" for v in hb.values()) and \
        all(v == "passed" for v in hf.values()) and not out["fixed"]["error"]
    if gws:
        out["gateways"] = {"len_buggy": len(gws["buggy"]), "len_fixed": len(gws["fixed"])}
        (RESULTS / f"{tid}_gateway_buggy.txt").write_text(gws["buggy"], encoding="utf-8")
        (RESULTS / f"{tid}_gateway_fixed.txt").write_text(gws["fixed"], encoding="utf-8")
    return out


def real_chat_fn(settings, gateway):
    def chat_fn(messages, tool_schemas):
        try:
            return gateway.chat(messages, tool_schemas, settings=settings, use_cache=True,
                                max_tokens=MAX_TOKENS, temperature=0.0)
        except gateway.GatewayError as e:
            cause = e.__cause__
            hdr = getattr(getattr(cause, "response", None), "headers", None)
            extra = ""
            if hdr is not None:
                extra = f" | retry-after={hdr.get('retry-after')}"
            body = getattr(cause, "body", None)
            if body:
                extra += f" | body={str(body)[:300]}"
            raise gateway.GatewayError(str(e) + extra) from e
    return chat_fn


def run_task(task, base, chat_fn, guard, counter, gateway_error) -> dict:
    tid = task["id"]
    tree, hidden = worktree.build_visible(task, tid, buggy=True)
    rec: dict = {}
    try:
        tb = tools.Toolbox(tree, hidden_names=set(hidden))
        t0 = time.monotonic()
        rec = agent_loop.run_agent(
            task, tb, chat_fn, guard=guard, counter=counter, gateway_error=gateway_error,
            save=lambda r: jwrite(RESULTS / f"{tid}.json", r))
        rec["wall_s"] = round(time.monotonic() - t0, 1)
        rec["files_modified"] = sorted(tb.files_modified)
        rec["files_created"] = sorted(tb.files_created)
        rec["edits"] = tb.edits
        rec["test_runs"] = tb.test_runs
        rec["root_cause"] = scoring.root_cause(task, rec["submitted"])
        rec["self_correction"] = scoring.self_correction(tb.test_runs)
        rec["tool_reliability"] = scoring.tool_reliability(rec["stats"])
        rec["repair"] = scoring.score_repair(task, tree, hidden, base, f"{tid}_score")
        if task["kind"] == "repair_and_test":
            rec["mutation"] = scoring.mutation_score(
                task, tree, (RESULTS / f"{tid}_gateway_fixed.txt").read_text(encoding="utf-8"),
                (RESULTS / f"{tid}_gateway_buggy.txt").read_text(encoding="utf-8"), f"{tid}_mut")
        rec["repair_success"] = bool(rec["repair"]["hidden_all_pass"]
                                     and rec["repair"]["no_regression"]
                                     and rec.get("mutation", {"mutation_valid": True})["mutation_valid"])
        rec["tokens_in"] = sum(s["tokens_in"] for s in rec["steps"])
        rec["tokens_out"] = sum(s["tokens_out"] for s in rec["steps"])
        rec["diff_files"] = {p: (tree / p).read_text(encoding="utf-8", errors="replace")
                             for p in rec["files_modified"] + rec["files_created"]}
        rec["complete"] = True
        jwrite(RESULTS / f"{tid}.json", rec)
    finally:
        worktree.cleanup(tree)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="T1,T2,T3,T4")
    ap.add_argument("--cap", type=int, default=60)
    ap.add_argument("--baseline-only", action="store_true")
    a = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    from traceforge.agent import beatapi, gateway
    from traceforge.config import Settings

    settings = Settings(llm_provider="beatapi", llm_model=MODEL, llm_free_only=True,
                        llm_cache_dir=RESULTS / "cache", llm_call_log=RESULTS / "llm_calls.jsonl")
    assert settings.llm_model == beatapi.FREE_MODEL == MODEL and MAX_TOKENS >= 2000
    key = settings.beatapi_api_key.get_secret_value()
    guard = usage_guard.UsageGuard(lambda: usage_guard.fetch_usage(key), RESULTS / "usage_snapshots.json")
    counter = agent_loop.LiveCounter(cap=a.cap)
    for p in RESULTS.glob("T?.json"):  # already-used live requests count against the cap
        counter.live += json.loads(p.read_text(encoding="utf-8")).get("live_requests", 0)
    chat_fn = real_chat_fn(settings, gateway)
    try:
        guard.check("start")
        for tid in a.tasks.split(","):
            task = load_task(tid)
            bf = RESULTS / f"baseline_{tid}.json"
            if not bf.exists():
                print(f"[{tid}] baseline ...", flush=True)
                jwrite(bf, baseline(task))
            base = json.loads(bf.read_text(encoding="utf-8"))
            print(f"[{tid}] baseline reproduces={base['reproduces']}", flush=True)
            if not base["reproduces"]:
                print(f"[{tid}] reconstruction does NOT reproduce: skipped, not substituted")
                continue
            if a.baseline_only:
                continue
            done = RESULTS / f"{tid}.json"
            if done.exists() and json.loads(done.read_text(encoding="utf-8")).get("complete"):
                print(f"[{tid}] already complete, skipping")
                continue
            print(f"[{tid}] agent run (live so far {counter.live}/{a.cap})", flush=True)
            rec = run_task(task, base, chat_fn, guard, counter, gateway.GatewayError)
            guard.check(f"{tid} done")
            print(f"[{tid}] done: requests={rec['requests']} repair_success={rec['repair_success']} "
                  f"auto_root_cause={rec['root_cause']['auto_correct']}", flush=True)
    except (agent_loop.StopRun, usage_guard.UsageAnomaly) as e:
        print("STOP:", e, flush=True)
        jwrite(RESULTS / "STOPPED.json", {"reason": str(e), "time": time.strftime("%F %T"),
                                          "live_requests": counter.live})
        return 2
    finally:
        print("worktrees left:", worktree.list_worktrees(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
