# ruff: noqa: E501
"""Offline scoring of dev-d1 patch-stage runs (EVALUATION ONLY: reads gold labels and mutation patches).

Per case and arm: was a patch generated, did it apply, which files and lines changed, did the
visible tests pass, did the hidden tests pass (counts only; hidden names are never stored), did a
test that passed before the patch fail after it (visible-suite regressions; the hidden suite is
reported as pass/fail counts only), tokens and latency, and whether the patch fixed the diagnosed
fault. "Fixed" = the reproducer and visible suite pass AND the hidden suite passes (TEST_VERIFIED).
Gold information (gold line range, the reverse of the mutation patch) is used here only to describe
how a patch relates to the known fix; it never reaches a prompt.
Usage: python -m traceforge.evaluation.patch_eval --manifest M --run L0=DIR --run G0=DIR [--out F]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from traceforge.repair.diffstats import changed_lines


def _read(p: Path):
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def _gold_fix_lines(datasets: Path, case_id: str) -> dict[str, tuple[list[str], list[str]]] | None:
    """The gold fix = the reverse of the mutation: it removes the mutated lines, adds the originals."""
    patch = datasets / "cases" / case_id / "mutation.patch"
    if not patch.exists():
        return None
    return {
        p: (added, removed)
        for p, (removed, added) in changed_lines(patch.read_text("utf-8")).items()
    }


def _regressions(baseline: dict | None, outcomes: dict | None) -> list[str] | None:
    if baseline is None or outcomes is None:
        return None
    return sorted(
        t for t, o in baseline.items() if o == "passed" and outcomes.get(t, "missing") != "passed"
    )


def score_case(run_dir: Path, case: dict, datasets: Path) -> dict | None:
    cid = case["case_id"]
    rec = _read(run_dir / "records" / f"{cid}.r0.json")
    d = run_dir / "cases" / f"{cid}.r0"
    if rec is None:
        return None
    meta, rep = _read(d / "run_meta.json") or {}, _read(d / "repair.json") or {}
    base = _read(d / "baseline_visible.json")
    reqs = [json.loads(x) for x in (d / "requests.jsonl").read_text("utf-8").splitlines()]
    atts = rep.get("attempts") or []
    applied = [a for a in atts if a["has_diff"]]
    final = applied[-1] if applied else None
    diff = (d / f"attempt{final['n']}.diff").read_text("utf-8") if final else ""
    stats = final["diff_stats"] if final else None
    diag_target = (rec["diagnosis"].get("target") or "").split("::")[0]
    gold_syms = case["gold_symbols"]
    lines_in_gold = None
    if stats and gold_syms:
        lo, hi = gold_syms[0]["start_line"], gold_syms[0]["end_line"]
        spans = [
            ln
            for f in stats["files"].values()
            for ln in (*f["removed_at"], *(max(1, x) for x in f["added_after"]))
        ]
        lines_in_gold = bool(spans) and all(lo - 1 <= ln <= hi for ln in spans)
    gold = _gold_fix_lines(datasets, cid)
    cl = changed_lines(diff) if diff else {}
    exact_gold = bool(cl) and gold is not None and {p: v for p, v in cl.items()} == gold
    reg = _regressions(base, final["visible_outcomes"]) if final else None
    hid = rep.get("hidden_counts")
    return {
        "case": cid, "site": case["variant_group"], "arm": rec["condition"],
        "diag_target": rec["diagnosis"].get("target"),
        "outcome": rec["outcome"], "reason": rec["failure_reason"],
        "attempts": len(atts),
        "patch_generated": bool(applied) or any(a["reasons"] for a in atts),
        "patch_applied": final is not None,
        "attempt_reasons": [a["reasons"] for a in atts],
        "files": sorted(stats["files"]) if stats else [],
        "lines_added": stats["added"] if stats else 0, "lines_removed": stats["removed"] if stats else 0,
        "removed_at": {f: v["removed_at"] for f, v in stats["files"].items()} if stats else {},
        "touches_diagnosed_file": bool(stats) and any(f.endswith(diag_target) for f in stats["files"]) if diag_target else None,
        "lines_within_gold_function": lines_in_gold, "exact_gold_equivalent": exact_gold,
        "reproducer_passed": bool(final and final.get("counts") and final["counts"]["repro_failed"] == 0 and final["counts"]["repro_passed"] > 0),
        "visible_passed": bool(final and final["visible_passed"]),
        "visible_counts": final["counts"] if final else None,
        "regressions_visible": reg, "n_regressions_visible": None if reg is None else len(reg),
        "hidden_passed": rep.get("hidden_passed"), "hidden_counts": hid,
        "fixed": rec["outcome"] == "TEST_VERIFIED_IN_LAB",
        "tokens_in": rec["tokens_in"], "tokens_out": rec["tokens_out"],
        "latency_ms": rec["latency_ms"], "model_s": (meta.get("timings") or {}).get("model_s"),
        "requests": len(reqs), "request_errors": [r.get("error") for r in reqs if r.get("error")],
        "cache_hits": rec["cache_hits"], "tier": meta.get("tier"), "stage": meta.get("stage"),
        "patch_source": meta.get("patch_source"), "diagnose_requests": sum(1 for r in reqs if r["stage"] == "diagnose"),
        "feedback_received": any(a.get("feedback_received") for a in atts),
    }  # fmt: skip


def summarize(rows: list[dict]) -> dict:
    out: dict = {}
    for arm in sorted({r["arm"] for r in rows}):
        rs = [r for r in rows if r["arm"] == arm]
        sites: dict = defaultdict(list)
        for r in rs:
            sites[r["site"]].append(r)
        out[arm] = {
            "cases": len(rs),
            "patch_generated": sum(r["patch_generated"] for r in rs),
            "patch_applied": sum(r["patch_applied"] for r in rs),
            "visible_passed": sum(r["visible_passed"] for r in rs),
            "hidden_passed": sum(bool(r["hidden_passed"]) for r in rs),
            "fixed": sum(r["fixed"] for r in rs),
            "with_visible_regressions": sum(bool(r["regressions_visible"]) for r in rs),
            "exact_gold_equivalent": sum(r["exact_gold_equivalent"] for r in rs),
            "tokens_in": sum(r["tokens_in"] for r in rs), "tokens_out": sum(r["tokens_out"] for r in rs),
            "requests": sum(r["requests"] for r in rs),
            "sites": {s: {"cases": len(v), "fixed": sum(x["fixed"] for x in v)} for s, v in sites.items()},
            "sites_with_a_fix": sum(any(x["fixed"] for x in v) for v in sites.values()),
        }  # fmt: skip
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--run", action="append", required=True, help="LABEL=run_dir (repeatable)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    datasets = a.manifest.resolve().parents[1]
    cases = {c["case_id"]: c for c in json.loads(a.manifest.read_text("utf-8"))}
    rows = []
    for spec in a.run:
        label, _, path = spec.partition("=")
        for case in cases.values():
            r = score_case(Path(path), case, datasets)
            if r:
                r["run"] = label
                rows.append(r)
    doc = {"rows": rows, "summary": summarize(rows)}
    if a.out:
        a.out.write_text(json.dumps(doc, indent=1), "utf-8")
    print(json.dumps(doc["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
