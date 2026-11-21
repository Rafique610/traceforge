"""Aggregate per-run records into results.json and a Markdown summary table."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from statistics import mean
from typing import Any

from scoring import consistency

Metric = Callable[[dict[str, Any]], "bool | None"]


def _patch(r: dict[str, Any], key: str) -> bool | None:
    """Patch metrics count over all runs of a repairable task (no patch = failure)."""
    if not r["patch_expected"]:
        return None
    p = r["patch"]
    return bool(p and p.get(key))


METRICS: dict[str, Metric] = {
    "class": lambda r: r["class_ok"],
    "target": lambda r: r["target_ok"],
    "grounded": lambda r: r["grounded"],
    "abstain_ok": lambda r: (
        r["abstain_correct"] if r["truth_class"] == "insufficient_evidence" else None
    ),
    "wrong_abstain": lambda r: (
        r["wrong_abstain"] if r["truth_class"] != "insufficient_evidence" else None
    ),
    "schema": lambda r: r["schema_ok"],
    "applies": lambda r: _patch(r, "applies"),
    "policy": lambda r: _patch(r, "policy_ok"),
    "hidden": lambda r: _patch(r, "hidden_pass"),
    "injection": lambda r: r["injection_resisted"],
}


def frac(records: list[dict[str, Any]], fn: Metric) -> tuple[int, int]:
    vals = [v for v in (fn(r) for r in records) if v is not None]
    return sum(bool(v) for v in vals), len(vals)


def _cell(pair: tuple[int, int]) -> str:
    return f"{pair[0]}/{pair[1]}" if pair[1] else "-"


def task_row(task_id: str, recs: list[dict[str, Any]]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "task": task_id,
        "runs": len(recs),
        "truth": recs[0]["truth_class"],
    }
    for name, fn in METRICS.items():
        row[name] = frac(recs, fn)
    diffs = [
        r["patch"]["diff_lines"]
        for r in recs
        if r["patch"] and r["patch"].get("diff_lines")
    ]
    row.update(
        invalid_tool_calls=sum(r["invalid_tool_calls"] for r in recs),
        tool_calls=sum(r["tool_calls"] for r in recs),
        expected_calls=mean(r["expected_calls_frac"] for r in recs),
        truncated=sum(r["truncated"] for r in recs),
        diff_lines=mean(diffs) if diffs else None,
        consistency=consistency(recs),
        tokens_in=sum(r["tokens_in"] for r in recs),
        tokens_out=sum(r["tokens_out"] for r in recs),
        latency_s=mean(r["latency_ms"] for r in recs) / 1000,
        infra_failures=sum(r["infra_failure"] for r in recs),
    )
    return row


def aggregate(records: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
    by_task: dict[str, list] = defaultdict(list)
    for r in records:
        by_task[r["task"]].append(r)
    rows = [task_row(t, rs) for t, rs in sorted(by_task.items())]
    totals = {name: frac(records, fn) for name, fn in METRICS.items()}
    cons = [row["consistency"] for row in rows if row["consistency"] is not None]
    totals.update(
        invalid_tool_calls=sum(r["invalid_tool_calls"] for r in records),
        truncated=sum(r["truncated"] for r in records),
        consistency=mean(cons) if cons else None,
        tokens_in=sum(r["tokens_in"] for r in records),
        tokens_out=sum(r["tokens_out"] for r in records),
        latency_s=mean(r["latency_ms"] for r in records) / 1000 if records else 0.0,
        infra_failures=sum(r["infra_failure"] for r in records),
    )
    return {"meta": meta, "totals": totals, "tasks": rows, "runs": records}


def to_markdown(agg: dict[str, Any]) -> str:
    m, t = agg["meta"], agg["totals"]
    lines = [
        f"# Smoke test: {m['provider']} / {m['model']}",
        "",
        f"**SMOKE TEST ONLY**: {len(agg['tasks'])} synthetic tasks x K={m['k']} runs, temperature 0. "
        "Counts are tiny; this is not a benchmark and differences of one run are noise.",
        "",
        f"- live requests this invocation: {m.get('live_requests', '?')} "
        f"(cap {m.get('max_requests') or 'none'}); incomplete: {m.get('incomplete', False)}",
        f"- infra failures (provider errors; those runs are retried on the next invocation): {t['infra_failures']}",
        "",
        "Cells are `passed/applicable` runs. `wrong_abstain` and `invalid`/`trunc` are bad when non-zero.",
        "",
        "| task | truth | class | target | grounded | abstain ok | wrong abst | schema | applies | policy | hidden | inject | invalid | trunc | diff lines | consist | tok in/out | lat s |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    def line(name: str, r: dict[str, Any], truth: str = "") -> str:
        d = r.get("diff_lines")
        c = r.get("consistency")
        return (
            f"| {name} | {truth} | "
            + " | ".join(_cell(r[k]) for k in METRICS)
            + f" | {r['invalid_tool_calls']} | {r['truncated']} | {'-' if d is None else f'{d:.0f}'} | "
            + f"{'-' if c is None else f'{c:.2f}'} | {r['tokens_in']}/{r['tokens_out']} | {r['latency_s']:.1f} |"
        )

    lines += [line(r["task"], r, r["truth"]) for r in agg["tasks"]]
    lines.append(line("**ALL**", {**t, "diff_lines": None}, ""))
    return "\n".join(lines) + "\n"
