# ruff: noqa: E501
"""CLI: `python -m traceforge.retrieval_bench --suite repos|dev|both --methods RET-L RET-G`.

Writes results/retrieval/<run_id>/. No model, no provider, no network. Never touches results/final.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from traceforge.retrieval_bench import methods as _methods  # noqa: F401  (registers RET-L/RET-G)
from traceforge.retrieval_bench import registry
from traceforge.retrieval_bench.dev_loader import DEV_MANIFEST, load_dev
from traceforge.retrieval_bench.packing import DEFAULT_BUDGET
from traceforge.retrieval_bench.report import provenance, write_run
from traceforge.retrieval_bench.runner import compare, run, summarize
from traceforge.retrieval_bench.suite import BENCH_DIR, REPO_ROOT, load_pins, load_workload


def review_sheet(bench_dir: Path, out: Path) -> int:
    """CSV for the second reviewer: one row per (query, gold unit); agree/disagree left blank."""
    n = 0
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["repo", "query_id", "query_type", "query_text", "gold_unit", "justification",
                    "reviewer_agree_yes_no", "reviewer_comment"])  # fmt: skip
        for pin in load_pins(bench_dir):
            for q in json.loads((bench_dir / pin["queries"]).read_text("utf-8"))["queries"]:
                for g in q["gold"]:
                    w.writerow(
                        [pin["name"], q["id"], q["type"], q["text"], g["id"], g["why"], "", ""]
                    )
                    n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="traceforge.retrieval_bench")
    ap.add_argument("--suite", choices=["repos", "dev", "both"], default="both")
    ap.add_argument("--methods", nargs="+", default=["RET-L", "RET-G"])
    ap.add_argument("--plugin", action="append", default=[], help="module that registers methods")
    ap.add_argument("--k", type=int, default=50)
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--run-id")
    ap.add_argument("--out-root", type=Path, default=REPO_ROOT / "results" / "retrieval")
    ap.add_argument("--dev-manifest", type=Path, default=DEV_MANIFEST)
    ap.add_argument("--no-rebuild-v5", action="store_true")
    ap.add_argument("--review-sheet", type=Path, help="write the second-reviewer CSV and exit")
    a = ap.parse_args(argv)
    if a.review_sheet:
        print(f"{review_sheet(BENCH_DIR, a.review_sheet)} rows -> {a.review_sheet}")
        return 0
    if "final" in a.out_root.parts:
        raise SystemExit("refusing to write under results/final")
    registry.load_plugins(a.plugin)
    started = time.time()
    run_id = a.run_id or "ret-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    pins = load_pins()
    workloads, skipped, extra = [], [], {}
    files = {"repos.json": BENCH_DIR / "repos.json"}
    if a.suite in ("repos", "both"):
        for pin in pins:
            workloads.append(load_workload(pin))
            files[pin["queries"]] = BENCH_DIR / pin["queries"]
    if a.suite in ("dev", "both"):
        dev, skipped, info = load_dev(a.dev_manifest, rebuild_v5=not a.no_rebuild_v5)
        workloads += dev
        extra["dev"] = info
        files["dev.json"] = a.dev_manifest
    result = run(workloads, a.methods, a.k, a.budget, a.repeats)
    summary = summarize(result["rows"], a.methods)
    comps = compare(result["rows"], a.methods)
    prov = provenance(a.methods, result, pins, files, extra, started)
    out = a.out_root / run_id
    write_run(out, result, summary, comps, prov, a.methods, skipped)
    print(f"written {out}")
    for r in summary:
        if r["qtype"] == "ALL":
            print(f"{r['suite']:<22}{r['method']:<8}n={r['n']:<3} R@10={r['recall@10']:.3f} "
                  f"MRR={r['mrr']:.3f} nDCG@10={r['ndcg@10']:.3f} cov={r['gold_coverage_packed']:.3f}")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
