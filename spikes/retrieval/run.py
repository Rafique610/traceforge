"""P0-S06 Part A: run 5 real faults, rank with R0/trace/L/G, score, save JSON.

Run: task spike:retrieval   (or: uv run --no-project --python 3.12 python spikes/retrieval/run.py)
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from index import build
from rank import grep_terms, query_terms, rank_graph, rank_lexical, rank_ripgrep, rank_trace_only, trace_nodes

HERE = Path(__file__).parent
TOYSHOP = HERE / "toyshop"
OUT = HERE / "results" / "retrieval.json"

FAULTS = [
    {
        "id": "F1-empty-cart",
        "class": "application_code",
        "declared_distance": 0,
        "file": "orders.py",
        "find": "    if not items:\n        return 0.0\n",
        "replace": "",
        "env": {},
        "repro": "api.checkout_handler({'items': []})",
        "gold": "fn:orders.py::order_total",
    },
    {
        "id": "F2-zero-qty",
        "class": "application_code",
        "declared_distance": 0,
        "file": "pricing.py",
        "find": "return total / qty if qty else 0.0",
        "replace": "return total / qty",
        "env": {},
        "repro": "api.price_quote({'total': 10, 'qty': 0})",
        "gold": "fn:pricing.py::unit_price",
    },
    {
        "id": "F3-redis-host",
        "class": "configuration",
        "declared_distance": 1,
        "file": None,
        "env": {"REDIS_HOST": "redsi"},
        "repro": "api.resend_email({'order_id': 7})",
        "gold": "cfg:REDIS_HOST",
    },
    {
        "id": "F4-pool-size",
        "class": "configuration",
        "declared_distance": 1,
        "file": None,
        "env": {"DB_POOL_SIZE": "0"},
        "repro": "api.list_products()",
        "gold": "cfg:DB_POOL_SIZE",
    },
    {
        "id": "F5-qty-string",
        "class": "application_code",
        "declared_distance": 2,
        "file": "cart.py",
        "find": "return int(raw)",
        "replace": "return raw.strip()",
        "env": {},
        "repro": "api.checkout_handler({'items': [{'sku': 'A', 'price': '5.0', 'qty': ' 2'}]})",
        "gold": "fn:cart.py::parse_qty",
    },
]
METHODS = ["R0_ripgrep", "trace_only", "L_bm25_anchor", "G_graph"]


def reproduce(fault: dict, workdir: Path) -> str:
    """Copy the clean app, inject the fault, run the reproducer, return the real traceback."""
    shutil.copytree(TOYSHOP, workdir, dirs_exist_ok=True)
    if fault["file"]:
        p = workdir / fault["file"]
        src = p.read_text(encoding="utf-8")
        assert fault["find"] in src, fault["id"]
        p.write_text(src.replace(fault["find"], fault["replace"], 1), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("REDIS_", "DB_", "TAX_", "DISCOUNT_"))}
    env["REDIS_HOST"] = "localhost"  # clean default resolves
    env.update(fault["env"])
    code = f"import api; api.{fault['repro'].removeprefix('api.')}"
    res = subprocess.run(
        [sys.executable, "-c", code], cwd=workdir, env=env, capture_output=True, text=True, timeout=60
    )
    assert res.returncode != 0, f"{fault['id']} did not fail"
    return res.stderr


def check_clean() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(TOYSHOP, tmp, dirs_exist_ok=True)
        for f in FAULTS:
            env = dict(os.environ, REDIS_HOST="localhost")
            r = subprocess.run(
                [sys.executable, "-c", f"import api; api.{f['repro'][4:]}"],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert r.returncode == 0, f"clean app fails on {f['id']}: {r.stderr[-300:]}"


def main() -> None:
    check_clean()
    results = []
    for fault in FAULTS:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "app"
            stderr = reproduce(fault, work)
            idx = build(work)
            terms = query_terms(idx, stderr)
            rg_terms = grep_terms(idx, stderr)
            anchors = trace_nodes(idx, stderr)
            graph_distance = idx.hops(set(anchors), 5).get(fault["gold"])
            row = {
                "fault": fault["id"],
                "class": fault["class"],
                "declared_distance": fault["declared_distance"],
                "graph_distance_from_trace": graph_distance,
                "gold": fault["gold"],
                "error_line": stderr.strip().splitlines()[-1],
                "trace_nodes": anchors,
                "query_terms": terms,
                "grep_terms": rg_terms,
                "methods": {},
            }
            runs = [
                ("R0_ripgrep", rank_ripgrep, (idx, rg_terms)),
                ("trace_only", rank_trace_only, (idx, stderr)),
                ("L_bm25_anchor", rank_lexical, (idx, stderr, terms)),
                ("G_graph", rank_graph, (idx, stderr, terms)),
            ]
            for name, fn, args in runs:
                t0 = time.perf_counter()
                ranked = fn(*args)
                ms = (time.perf_counter() - t0) * 1000
                rank = ranked.index(fault["gold"]) + 1 if fault["gold"] in ranked else None
                row["methods"][name] = {"rank": rank, "top5": ranked[:5], "ms": round(ms, 2)}
            results.append(row)
            code_map = idx.code_map
    summary = {}
    for m in METHODS:
        ranks = [r["methods"][m]["rank"] for r in results]
        summary[m] = {
            "recall_at_1": sum(1 for x in ranks if x == 1) / len(ranks),
            "recall_at_5": sum(1 for x in ranks if x and x <= 5) / len(ranks),
            "recall_at_10": sum(1 for x in ranks if x and x <= 10) / len(ranks),
            "mrr": round(sum(1 / x for x in ranks if x) / len(ranks), 3),
            "median_ms": sorted(r["methods"][m]["ms"] for r in results)[len(results) // 2],
        }
    rg = subprocess.run(
        [shutil.which("rg"), "--version"], capture_output=True, text=True
    ).stdout.splitlines()[0]
    out = {
        "python": platform.python_version(),
        "ripgrep": rg,
        "faults": results,
        "summary": summary,
        "code_map": {
            "text": code_map,
            "chars": len(code_map),
            "approx_tokens_chars_div_4": len(code_map) // 4,
        },
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    for r in results:
        print(r["fault"], "d=", r["graph_distance_from_trace"], {m: r["methods"][m]["rank"] for m in METHODS})
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
