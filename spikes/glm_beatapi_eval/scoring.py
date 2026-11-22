"""Scoring. Repair success needs the hidden test to pass; an explanation alone never counts.
Root-cause correctness is judged automatically by gold keywords/locations and needs human review."""

from __future__ import annotations

import re
from pathlib import Path

import sandbox_exec
import worktree


def hidden_names(task: dict) -> list[str]:
    return [n for h in task.get("hidden", []) for n in h["names"]] + task.get("hidden_ids", [])


def root_cause(task: dict, submitted: dict | None) -> dict:
    gold = task["gold"]
    if not submitted:
        return {"auto_correct": False, "reason": "no submit_final", "needs_human_review": True}
    text = " ".join(submitted.values())
    low = text.lower()
    files = {f: (Path(f).name in text or f in text) for f in gold["files"]}
    funcs = {fn: (fn in text) for fn in gold["functions"]}
    groups = [any(re.search(p, text, re.I) for p in g) for g in gold["mechanism"]]
    main = submitted.get("root_cause_file", "").replace("\\", "/")
    main_ok = any(f.endswith(main) or main.endswith(Path(f).name) for f in gold["files"]) and bool(main)
    all_files = all(files.values())
    auto = main_ok and any(funcs.values()) and all(groups) and all_files
    return {"auto_correct": auto, "auto_correct_lenient": main_ok and all(groups),
            "main_file_ok": main_ok, "files_named": files,
            "functions_named": funcs, "mechanism_groups_hit": groups,
            "all_gold_files_named": all_files, "len_chars": len(low),
            "needs_human_review": True,
            "note": "judged automatically by gold file/function/keyword match; needs human review"}


def self_correction(test_runs: list[dict]) -> dict:
    """A later run_tests showing fewer failures after at least one edit, following a failing run."""
    for i, a in enumerate(test_runs):
        if a["failed"] <= 0:
            continue
        for b in test_runs[i + 1:]:
            if b["edits_before"] > a["edits_before"] and b["failed"] < a["failed"] and not b["error"]:
                return {"detected": True, "failed_before": a["failed"], "failed_after": b["failed"]}
    return {"detected": False}


def tool_reliability(stats: dict) -> dict:
    keys = ("tool_calls", "tool_ok", "tool_tool_error", "tool_unknown_tool", "tool_bad_args",
            "no_tool_call_turns", "repeated_identical_call_loops", "finish_length", "no_submit")
    out = {k: stats.get(k, 0) for k in keys}
    out["tool_ok"] = out["tool_calls"] - out["tool_tool_error"] - out["tool_unknown_tool"] - \
        out["tool_bad_args"]
    return out


def _outcomes(r: dict) -> dict[str, str]:
    return {n: o for n, o in r["tests"]}


def score_repair(task: dict, final_tree: Path, hidden: dict[str, str], baseline: dict,
                 name: str, run=sandbox_exec.run_pytest) -> dict:
    """Run the package tests + hidden tests on a scorer copy of the model's final tree."""
    sc = worktree.scorer_copy(final_tree, hidden, name)
    try:
        r = run(sc, task["package_tests"], 300, 2500)
    finally:
        worktree.remove_scorer(sc)
    out = _outcomes(r)
    hid = hidden_names(task)
    hidden_res = {n: out.get(n, "missing") for n in hid}
    ref_pass = set(baseline.get("fixed_passing", []))
    buggy_pass = set(baseline.get("buggy_passing", []))
    failing = {n for n, o in out.items() if o in ("failed", "error")}
    regress = sorted((failing & buggy_pass) - set(hid))
    residual = sorted((failing & ref_pass) - set(hid) - set(regress))
    return {"hidden_results": hidden_res,
            "hidden_all_pass": bool(hid) and all(v == "passed" for v in hidden_res.values()),
            "package_passed": r["passed"], "package_failed": r["failed"],
            "regressions": regress, "residual_failures_vs_reference": residual,
            "no_regression": not regress and not residual,
            "sandbox_error": r["error"], "tail": r["tail"][-1200:]}


def mutation_score(task: dict, final_tree: Path, fixed_gateway: str, buggy_gateway: str,
                   name: str, run=sandbox_exec.run_pytest) -> dict:
    """T4: the model's own new test file must FAIL on buggy gateway.py and PASS on the fixed one."""
    rel = task["required_test_file"]
    if not (final_tree / rel).is_file():
        return {"test_file_present": False, "mutation_valid": False}
    res: dict = {"test_file_present": True}
    for label, content in (("buggy", buggy_gateway), ("fixed", fixed_gateway)):
        sc = worktree.scorer_copy(final_tree, {}, f"{name}_{label}")
        try:
            gw = sc / "backend/traceforge/agent/gateway.py"
            gw.write_bytes(content.encode("utf-8"))
            r = run(sc, [rel.removeprefix("backend/")], 240, 1500)
        finally:
            worktree.remove_scorer(sc)
        outs = [o for _, o in r["tests"]]
        res[label] = {"n_tests": len(outs), "passed": r["passed"], "failed": r["failed"],
                      "outcomes": r["tests"], "error": r["error"], "tail": r["tail"][-800:]}
    b, f = res["buggy"], res["fixed"]
    res["fails_on_buggy"] = b["n_tests"] > 0 and any(o == "failed" for _, o in b["outcomes"]) \
        and not any(o == "error" for _, o in b["outcomes"])
    res["passes_on_fixed"] = f["n_tests"] > 0 and f["failed"] == 0 and not f["error"]
    res["tests_added"] = f["n_tests"]
    res["mutation_valid"] = res["fails_on_buggy"] and res["passes_on_fixed"]
    return res
