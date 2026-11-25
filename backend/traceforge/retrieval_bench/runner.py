# ruff: noqa: E501
"""Run registered retrievers over workloads: same query text in, same shared packer, same metrics.
Gold is read only here, by the scorer, after the retriever has returned."""

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from typing import Any

from traceforge.retrieval_bench import registry
from traceforge.retrieval_bench.metrics import score_query
from traceforge.retrieval_bench.packing import DEFAULT_BUDGET, pack_ids
from traceforge.retrieval_bench.repo_ctx import measure_build_peak_bytes, process_peak_rss_mb
from traceforge.retrieval_bench.stats import ITERS, SEED, paired_bootstrap, sign_test
from traceforge.retrieval_bench.suite import Workload, assert_no_forbidden_paths
from traceforge.retrieval_bench.types import BenchQuery, QueryText

METRIC_KEYS = (
    "recall@1", "recall@5", "recall@10", "precision@1", "precision@5", "precision@10", "mrr",
    "ndcg@10", "file_hit@1", "file_hit@5", "symbol_hit@1", "gold_coverage_packed",
    "precision_packed", "mrr_packed", "tokens_used", "packed_hits", "latency_ms",
)  # fmt: skip
DIFF_METRICS = ("recall@5", "recall@10", "mrr", "ndcg@10", "gold_coverage_packed", "file_hit@1")


def _check_clean(q: BenchQuery) -> QueryText:
    """What a retriever receives: the QueryText only. Fails if a gold id leaked into its text."""
    t = q.text
    if type(t) is not QueryText:
        raise TypeError("retrievers must be given a QueryText")
    for g in q.gold:
        if g in str(t):
            raise AssertionError(f"gold id {g!r} appears in the query text of {q.qid}")
    return t


def run(
    workloads: list[Workload], methods: list[str], k: int = 50, budget: int = DEFAULT_BUDGET,
    repeats: int = 3, measure_memory: bool = True,
) -> dict[str, Any]:  # fmt: skip
    rows: list[dict] = []
    rankings: dict[str, dict] = {}
    builds: list[dict] = []
    for w in workloads:
        ctx = w.ctx
        assert_no_forbidden_paths(ctx)
        peak = measure_build_peak_bytes(ctx.root) if measure_memory else None
        base = {
            "suite": w.suite, "unit": ctx.name, "tier": w.tier, "chunks": ctx.n_chunks,
            "source_files": ctx.n_files(), "graph_build_s": ctx.graph_s,
            "corpus_build_s": ctx.corpus_s, "bm25_build_s": ctx.bm25_s,
            "base_build_s": ctx.build_s, "build_peak_py_heap_mb": peak and round(peak / 1e6, 2),
            "corpus_text_bytes": ctx.corpus_text_bytes(),
        }  # fmt: skip
        for m in methods:
            r = registry.get(m)
            t0 = time.perf_counter()
            if hasattr(r, "prepare"):
                r.prepare(ctx)
            prep = time.perf_counter() - t0
            builds.append(
                {**base, "method": m, "index_build_s": prep,
                 "storage_bytes": r.storage_bytes(ctx) if hasattr(r, "storage_bytes") else 0}
            )  # fmt: skip
            for q in w.queries:
                qt = _check_clean(q)
                lats, first = [], None
                for _ in range(repeats):
                    t0 = time.perf_counter()
                    ranked = r(ctx, qt, k)
                    lats.append((time.perf_counter() - t0) * 1000)
                    if first is not None and ranked != first:
                        raise AssertionError(f"{m} is not deterministic on {q.qid}")
                    first = ranked
                assert first is not None and len(first) <= k and len(set(first)) == len(first)
                packed = pack_ids(ctx, first, budget)
                sc = score_query(ctx, first, q.gold, packed)
                sc["latency_ms"] = statistics.median(lats)
                rows.append({"suite": w.suite, "unit": ctx.name, "qid": q.qid, "qtype": q.qtype,
                             "method": m, **sc})  # fmt: skip
                rankings.setdefault(m, {})[f"{w.suite}/{ctx.name}/{q.qid}"] = {
                    "ranked": first,
                    "packed": packed.ids,
                }
    return {"rows": rows, "rankings": rankings, "builds": builds, "k": k, "budget": budget,
            "repeats": repeats, "process_peak_rss_mb": process_peak_rss_mb()}  # fmt: skip


def _mean(v: list[float]) -> float:
    return sum(v) / len(v) if v else float("nan")


def summarize(rows: list[dict], methods: list[str]) -> list[dict]:
    """Mean of each metric per (suite, qtype, method); qtype 'ALL' pools a suite; suite 'ALL'
    pools every suite except dev (mean over queries, not over repos)."""
    out: list[dict] = []
    keyed: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        for suite in {r["suite"], *(["ALL"] if r["suite"] != "dev" else [])}:
            for qt in {r["qtype"], "ALL"}:
                keyed[(suite, qt, r["method"])].append(r)
    for (suite, qt, m), rs in sorted(keyed.items()):
        out.append({"suite": suite, "qtype": qt, "method": m, "n": len(rs),
                    **{k: _mean([x[k] for x in rs]) for k in METRIC_KEYS}})  # fmt: skip
    return out


def compare(
    rows: list[dict], methods: list[str], iters: int = ITERS, seed: int = SEED
) -> list[dict]:
    """Paired bootstrap CI + sign test for every method pair, per (suite, qtype)."""
    out: list[dict] = []
    by: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        by[(r["suite"], r["unit"], r["qid"])][r["method"]] = r
    for suite in sorted({r["suite"] for r in rows} | {"ALL"}):
        for qt in sorted({r["qtype"] for r in rows} | {"ALL"}):
            qs = [
                v for (s, _u, _q), v in sorted(by.items())
                if (s == suite or (suite == "ALL" and s != "dev"))
                and (qt == "ALL" or next(iter(v.values()))["qtype"] == qt)
            ]  # fmt: skip
            if not qs:
                continue
            for i, a in enumerate(methods):
                for b in methods[i + 1 :]:
                    for mt in DIFF_METRICS:
                        xa, xb = [v[a][mt] for v in qs], [v[b][mt] for v in qs]
                        bs = paired_bootstrap(xa, xb, iters, f"{seed}|{suite}|{qt}|{a}|{b}|{mt}")
                        out.append({"suite": suite, "qtype": qt, "a": a, "b": b, "metric": mt,
                                    **bs, **sign_test(xa, xb)})  # fmt: skip
    return out
