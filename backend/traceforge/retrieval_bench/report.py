# ruff: noqa: E501
"""Write results/retrieval/<run_id>/ : csv + json + md tables and a provenance block."""

from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

from traceforge.retrieval_bench import registry
from traceforge.retrieval_bench.runner import DIFF_METRICS, METRIC_KEYS
from traceforge.retrieval_bench.suite import REPO_ROOT, sha256_file


def _git(*a: str) -> str:
    try:
        return subprocess.run(  # noqa: S603
            ["git", "-C", str(REPO_ROOT), *a],
            capture_output=True,
            text=True,
            check=True,  # noqa: S607
        ).stdout.strip()
    except Exception:
        return "unavailable"


def _ver(pkg: str) -> str:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return "n/a"


def provenance(
    methods: list[str], result: dict, pins: list[dict], files: dict[str, Path], extra: dict,
    started: float,
) -> dict:  # fmt: skip
    from traceforge.evaluation.fingerprint import code_fingerprint

    return {
        "git_sha": _git("rev-parse", "HEAD"),
        "git_dirty_paths_count": len([ln for ln in _git("status", "--porcelain").splitlines() if ln]),
        "rc1_code_fingerprint": code_fingerprint(),
        "repo_pins": pins,
        "methods": {m: registry.meta(m) for m in methods},
        "model_ids": {m: registry.meta(m)["model_id"] for m in methods},
        "settings": {"k": result["k"], "token_budget": result["budget"], "reserve_fraction": 0.2,
                     "token_estimate": "chars/4", "latency_repeats_median": result["repeats"],
                     "bootstrap": {"iters": 10000, "seed": 20261125, "ci": "percentile 95%"}},
        "dataset_hashes": {k: sha256_file(p) for k, p in files.items() if p.is_file()},
        "hardware": {"platform": platform.platform(), "processor": platform.processor(),
                     "cpu_count": os.cpu_count(), "python": sys.version.split()[0]},
        "packages": {p: _ver(p) for p in ("rank-bm25", "networkx", "numpy", "pydantic")},
        "process_peak_rss_mb": result["process_peak_rss_mb"],
        "runtime_s": round(time.time() - started, 1),
        "llm_or_provider_calls": 0,
        **extra,
    }  # fmt: skip


def _csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", "utf-8")
        return
    keys = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, keys, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6f}" if isinstance(v, float) else v) for k, v in r.items()})


def _md_table(rows: list[dict], cols: list[str]) -> str:
    def f(v):
        return f"{v:.3f}" if isinstance(v, float) else str(v)

    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(f(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join(out)


def write_run(out: Path, result: dict, summary: list[dict], comps: list[dict], prov: dict,
              methods: list[str], skipped: list[dict] | None = None) -> None:  # fmt: skip
    out.mkdir(parents=True, exist_ok=True)
    _csv(out / "per_query.csv", result["rows"])
    _csv(out / "summary.csv", summary)
    _csv(out / "comparisons.csv", comps)
    _csv(out / "builds.csv", result["builds"])
    # rankings carry no timing: byte-identical across runs (determinism check)
    (out / "rankings.json").write_text(
        json.dumps(result["rankings"], indent=1, sort_keys=True), "utf-8"
    )
    (out / "summary.json").write_text(
        json.dumps({"provenance": prov, "summary": summary, "comparisons": comps,
                    "builds": result["builds"], "skipped": skipped or []}, indent=1), "utf-8")  # fmt: skip
    cols = ["suite", "qtype", "method", "n", "recall@1", "recall@5", "recall@10", "precision@5",
            "mrr", "ndcg@10", "file_hit@1", "gold_coverage_packed", "tokens_used", "latency_ms"]  # fmt: skip
    md = [f"# Retrieval benchmark run `{out.name}`", "",
          "Engineering validation only; small n; no superiority claim.", "",
          "## Provenance", "```json", json.dumps(prov, indent=1), "```", "",
          "## Summary (means over queries)", _md_table(summary, cols), "",
          f"## Paired differences ({', '.join(DIFF_METRICS)}): a - b, bootstrap 95% CI", ""]  # fmt: skip
    md.append(_md_table([c for c in comps if c["qtype"] == "ALL"],
                        ["suite", "a", "b", "metric", "n", "mean_diff", "ci_lo", "ci_hi", "a_better",
                         "b_better", "ties", "p"]))  # fmt: skip
    md += ["", "## Build cost per workload x method", _md_table(result["builds"][:60],
           ["unit", "method", "chunks", "source_files", "base_build_s", "index_build_s",
            "build_peak_py_heap_mb", "storage_bytes"])]  # fmt: skip
    if skipped:
        md += ["", "## Skipped", *[f"- {s['case_id']}: {s['reason']}" for s in skipped]]
    (out / "report.md").write_text("\n".join(md) + "\n", "utf-8")
    assert set(METRIC_KEYS) <= set(summary[0]) if summary else True
