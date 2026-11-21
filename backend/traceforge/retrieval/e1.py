"""E1: retrieval quality without any LLM. R0 ripgrep-style, trace-only, L and G on every repairable
case of a manifest, scored with `traceforge.evaluation.metrics` (Recall@1/5/10, MRR, nDCG@10).

    python -m traceforge.retrieval.e1 --manifest datasets/manifests/dev.json \
        --repo-root <tree root or dir of per-case trees> --evidence-dir <dir of EvidenceBundle JSON>

Per case the tree is `<repo-root>/<case_id>` when that directory holds `lab/`, else `<repo-root>`
itself when it holds `lab/`, else (generator output, `datasets/cases`) `<case_id>/mutation.patch`
applied to the pristine lab (manifest paths are repo-relative, `lab/worker/queue.py`). Evidence is
read from
`<evidence-dir>/<case_id>.json` or `<evidence-dir>/<case_id>/evidence_bundle.json`: collecting it
needs the live faulty lab, so cases without a saved bundle are listed as skipped, never invented.
Results go to `runs/e1/<run_id>/result.json` (+ every ContextBundle) with the manifest sha256.
"""

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from traceforge.codeintel import Graph, build_graph
from traceforge.contracts.case_manifest import REPAIRABLE, CaseManifest
from traceforge.contracts.context import ContextBundle
from traceforge.contracts.evidence import EvidenceBundle
from traceforge.evaluation.metrics.common import distance_bucket, gold_node_ids, group_by
from traceforge.evaluation.metrics.retrieval import retrieval_metrics
from traceforge.evaluation.runner import load_manifest
from traceforge.retrieval.baselines import r0_impl, run_baseline
from traceforge.retrieval.context_budget import RESERVE_FRACTION
from traceforge.retrieval.corpus import get_corpus
from traceforge.retrieval.graph_ranker import GraphFeatures
from traceforge.retrieval.lexical import index_for
from traceforge.retrieval.retrieve import G_WEIGHTS, L_WEIGHTS, TOP_K, retrieve

METHODS = ("R0", "trace_only", "L", "G")
DEFAULT_BUDGET = 3000  # tokens (chars/4): about 12,000 chars, the agent's default context budget


def _tree(repo_root: Path, case_id: str, scratch: Path) -> Path:
    """Tree of one case: `<root>/<case_id>/lab`, else `<root>` itself (when it holds `lab/`), else
    generator output `<root>/<case_id>/mutation.patch` applied to the pristine lab in `scratch`."""
    per_case = repo_root / case_id
    if (per_case / "lab").is_dir():
        return per_case
    if (repo_root / "lab").is_dir():
        return repo_root
    if (per_case / "mutation.patch").is_file():
        from traceforge.faultgen.generate import materialize

        return materialize((per_case / "mutation.patch").read_text("utf-8"), scratch / case_id)
    return repo_root


def _evidence(evidence_dir: Path | None, case_id: str) -> EvidenceBundle | None:
    for p in (
        (evidence_dir / f"{case_id}.json", evidence_dir / case_id / "evidence_bundle.json")
        if evidence_dir
        else ()
    ):
        if p.is_file():
            return EvidenceBundle.model_validate_json(p.read_text("utf-8"))
    return None


def _run(method: str, ev: EvidenceBundle, graph: Graph, budget: int, service: str) -> ContextBundle:
    if method in ("L", "G"):
        return retrieve(ev, graph, method, budget, service=service)
    return run_baseline(method, ev, graph, budget, service)


def _case_row(method: str, b: ContextBundle, m: CaseManifest, ms: float) -> dict:
    gold = gold_node_ids(m)
    ids = [h.node_id for h in b.hits]
    ranks = sorted(ids.index(g) + 1 for g in gold if g in ids)
    return {"case_id": m.case_id, "method": method, "first_gold_rank": ranks[0] if ranks else None,
            "gold_found": len(ranks), "gold": len(gold), "hits": len(ids),
            "tokens_used": b.tokens_used, "latency_ms": round(ms, 3)}  # fmt: skip


def _latency(rows: list[dict]) -> dict:
    v = [r["latency_ms"] for r in rows]
    if not v:
        return {"n": 0}
    return {"n": len(v), "mean": statistics.fmean(v), "median": statistics.median(v), "max": max(v)}


def _by(items: list, key) -> dict:
    return {k: retrieval_metrics(v) for k, v in group_by(items, key).items()}


def run_e1(
    manifest: Path, repo_root: Path, evidence_dir: Path | None, out_root: Path,
    token_budget: int = DEFAULT_BUDGET, run_id: str | None = None,
) -> dict:  # fmt: skip
    cases, sha = load_manifest(manifest)
    run_id = run_id or "e1-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = out_root / run_id
    graphs: dict[Path, tuple[Graph, float]] = {}
    items: dict[str, list] = {m: [] for m in METHODS}
    rows: list[dict] = []
    skipped: list[dict] = []
    for case in sorted(cases, key=lambda c: c.case_id):
        if case.cause_class not in REPAIRABLE:
            skipped.append(
                {"case_id": case.case_id, "reason": f"no retrieval target ({case.cause_class})"}
            )
            continue
        tree = _tree(repo_root, case.case_id, out / "trees")
        ev = _evidence(evidence_dir, case.case_id)
        if ev is None or not tree.is_dir():
            skipped.append(
                {
                    "case_id": case.case_id,
                    "reason": "no saved EvidenceBundle" if ev is None else f"tree {tree} missing",
                }
            )
            continue
        if tree not in graphs:
            t0 = time.perf_counter()
            g = build_graph(tree, cache_dir=None)
            index_for(
                get_corpus(g)
            )  # corpus + BM25 index built once per tree, outside query timing
            graphs[tree] = (g, time.perf_counter() - t0)
        graph = graphs[tree][0]
        for method in METHODS:
            t0 = time.perf_counter()
            bundle = _run(method, ev, graph, token_budget, case.service)
            ms = (time.perf_counter() - t0) * 1000
            items[method].append((bundle, case))
            rows.append(_case_row(method, bundle, case, ms))
            d = out / "bundles" / method
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{case.case_id}.json").write_text(
                json.dumps(
                    {
                        "method": method,
                        "case_id": case.case_id,
                        "bundle": bundle.model_dump(mode="json"),
                    },
                    indent=1,
                ),
                "utf-8",
            )
    methods = {}
    for m, its in items.items():
        mrows = [r for r in rows if r["method"] == m]
        methods[m] = {
            "overall": retrieval_metrics(its),
            "by_distance": _by(its, lambda it: distance_bucket(it[1].distance)),
            "by_fault_family": _by(its, lambda it: it[1].fault_family),
            "latency_ms": _latency(mrows),
        }  # fmt: skip
    result = {
        "run_id": run_id, "created": datetime.now(UTC).isoformat(), "manifest": str(manifest),
        "dataset_sha256": sha, "n_cases_in_manifest": len(cases), "n_scored": len(items["G"]),
        "skipped": skipped,
        "params": {
            "token_budget": token_budget, "reserve_fraction": RESERVE_FRACTION,
            "token_estimate": "chars/4 (approximation, not a tokenizer)", "bm25_top_k": TOP_K,
            "L_weights": vars(L_WEIGHTS), "G_weights": vars(G_WEIGHTS),
            "G_features": vars(GraphFeatures()), "r0_implementation": r0_impl(),
            "trace_only": "project trace-frame symbols, innermost first, nothing else",
            "baseline_bundle_mode_note": "R0/trace_only bundles carry mode=L (contract: L/G)",
            "latency_note": "per-query wall time, graph/corpus/index prebuilt",
            "weights_tuned": False,
        },
        "graph_build_s": {str(k): round(v[1], 3) for k, v in graphs.items()},
        "methods": methods, "cases": rows,
    }  # fmt: skip
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result, indent=1), "utf-8")
    return result


def format_table(result: dict) -> str:
    def val(d: dict, k: str) -> str:
        v = d[k]["value"] if isinstance(d.get(k), dict) else None
        return "  n/a" if v is None else f"{v:5.3f}"

    lines = [f"E1 {result['run_id']}  dataset_sha256={result['dataset_sha256'][:12]}  "
             f"scored={result['n_scored']}/{result['n_cases_in_manifest']}  "
             "(small n: pipeline check, no effect claimed)"]  # fmt: skip
    head = f"{'method':<11}{'bucket':<8}{'n':>3}  R@1   R@5   R@10  MRR   nDCG  tokens  ms(med)"
    lines.append(head)
    for m, r in result["methods"].items():
        groups = {"all": r["overall"], **{f"d={k}": v for k, v in r["by_distance"].items()}}
        for name, g in groups.items():
            tok = g["tokens_used"]["value"]
            lat = r["latency_ms"].get("median", float("nan")) if name == "all" else float("nan")
            lines.append(
                f"{m:<11}{name:<8}{g['n']:>3}  {val(g, 'recall@1')} {val(g, 'recall@5')} "
                f"{val(g, 'recall@10')} {val(g, 'mrr')} {val(g, 'ndcg@10')} "
                f"{'' if tok is None else round(tok):>6}  {lat:7.1f}"
            )  # fmt: skip
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="traceforge.retrieval.e1", description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--evidence-dir", type=Path)
    ap.add_argument("--token-budget", type=int, default=DEFAULT_BUDGET)
    ap.add_argument("--out-dir", type=Path, default=Path("runs/e1"))
    ap.add_argument("--run-id")
    a = ap.parse_args(argv)
    result = run_e1(
        a.manifest, a.repo_root.resolve(), a.evidence_dir, a.out_dir, a.token_budget, a.run_id
    )
    print(format_table(result))
    for s in result["skipped"]:
        print(f"skipped {s['case_id']}: {s['reason']}")
    print(f"written: {a.out_dir / result['run_id'] / 'result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
