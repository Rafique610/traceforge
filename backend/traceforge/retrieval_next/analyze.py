# ruff: noqa: E501, B007, E741
"""Preregistered analysis of the P5-S08 runs (reads the harness outputs, no retrieval, no model).

    python -m traceforge.retrieval_next.analyze --runs minilm=<dir> jina=<dir> nomic=<dir> \
        [--null4500 <dir>] --out results/retrieval/p5s08-analysis

Reads `per_query.csv` / `builds.csv` of each harness run, evaluates H1-H4 of
docs/research/embedding-hybrid-preregistration.md (primary model jina, both RRF k), the direct
comparisons (G vs RET-LGE vs RET-E vs the best hybrid), per-type and per-cause-class tables, and
cost. Paired bootstrap = traceforge.retrieval_bench.stats (10,000 resamples, seeded).
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from traceforge.retrieval_bench.stats import paired_bootstrap, sign_test

CORE = ("recall@1", "recall@5", "recall@10", "precision@5", "precision@10", "mrr", "ndcg@10",
        "file_hit@1", "gold_coverage_packed", "precision_packed", "tokens_used", "latency_ms")  # fmt: skip
RANKMETRICS = ("recall@10", "mrr", "ndcg@10", "gold_coverage_packed")
SEED = "20261125|p5s08"


def load(run: Path) -> list[dict]:
    rows = []
    for r in csv.DictReader((run / "per_query.csv").open(encoding="utf-8")):
        for k in r:
            if k not in ("suite", "unit", "qid", "qtype", "method"):
                r[k] = float(r[k])
        rows.append(r)
    return rows


def load_builds(run: Path) -> list[dict]:
    return list(csv.DictReader((run / "builds.csv").open(encoding="utf-8")))


class Data:
    """rows[(method)] -> {(suite, unit, qid): row}; method names are globally unique per model."""

    def __init__(self, runs: dict[str, Path], null: Path | None):
        self.by: dict[str, dict[tuple, dict]] = defaultdict(dict)
        self.model_of: dict[str, str] = {}
        self.run_of: dict[str, str] = {}
        base_ref: dict[str, dict] = {}
        for tag, path in runs.items():
            for r in load(path):
                m = r["method"]
                key = (r["suite"], r["unit"], r["qid"])
                if m in (
                    "RET-L",
                    "RET-G",
                ):  # baselines: first run is the reference, others must agree
                    ref = base_ref.setdefault(f"{m}|{key}", r)
                    for c in ("recall@10", "mrr", "gold_coverage_packed", "tokens_used"):
                        assert abs(ref[c] - r[c]) < 1e-9, (
                            m,
                            key,
                            c,
                            "baseline differs between runs",
                        )
                    self.by[m][key] = ref if key in self.by[m] else r
                else:
                    self.by[m][key] = r
                    self.model_of[m] = tag
                    self.run_of[m] = tag
        self.null = {}
        if null:
            for r in load(null):
                self.null.setdefault(r["method"], {})[(r["suite"], r["unit"], r["qid"])] = r

    def keys(self, sel: str) -> list[tuple]:
        ks = sorted(self.by["RET-L"])
        if sel == "repos":
            return [k for k in ks if k[0] != "dev"]
        if sel == "dev":
            return [k for k in ks if k[0] == "dev"]
        if sel.startswith("dev:"):
            return [k for k in ks if k[0] == "dev" and self.by["RET-L"][k]["qtype"] == sel[4:]]
        if sel.startswith("repos:"):
            return [k for k in ks if k[0] != "dev" and self.by["RET-L"][k]["qtype"] == sel[6:]]
        raise ValueError(sel)

    def mean(self, m: str, metric: str, sel: str) -> float:
        ks = self.keys(sel)
        return sum(self.by[m][k][metric] for k in ks) / len(ks) if ks else float("nan")

    def diff(self, a: str, b: str, metric: str, sel: str, src=None) -> dict:
        src = src or self.by
        ks = self.keys(sel)
        xa, xb = [src[a][k][metric] for k in ks], [src[b][k][metric] for k in ks]
        d = paired_bootstrap(xa, xb, 10_000, f"{SEED}|{sel}|{a}|{b}|{metric}")
        return {**d, **sign_test(xa, xb)}


def fmt(x, nd=3):
    return "n/a" if x != x else f"{x:.{nd}f}"


def ci(d) -> str:
    return f"{d['mean_diff']:+.3f} [{d['ci_lo']:+.3f}, {d['ci_hi']:+.3f}]"


def md_table(head: list[str], rows: list[list]) -> str:
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|",
                      *["| " + " | ".join(str(c) for c in r) + " |" for r in rows]])  # fmt: skip


def analyse(data: Data, primary: str) -> tuple[str, dict]:
    out: list[str] = []
    res: dict = {"primary": primary}
    methods = sorted(data.by)
    models = sorted({t for t in data.model_of.values()})

    def name(kind: str, tag: str, k: int | None = None) -> str:
        return f"RET-E@{tag}" if kind == "E" else f"RET-{kind}@{tag}:k{k}"

    # ---- headline tables
    sels = [("repos", "45 benchmark queries"), ("dev", "dev (all scored)"),
            ("dev:configuration", "dev configuration"), ("dev:application_code", "dev application_code")]  # fmt: skip
    for sel, title in sels:
        n = len(data.keys(sel))
        rows = []
        for m in ["RET-L", "RET-G"] + [
            x for x in methods if x.startswith("RET-") and x not in ("RET-L", "RET-G")
        ]:
            if m not in data.by:
                continue
            rows.append(
                [
                    m,
                    *[
                        fmt(data.mean(m, c, sel), 3 if c != "tokens_used" else 0)
                        if c != "latency_ms"
                        else fmt(data.mean(m, c, sel), 1)
                        for c in CORE
                    ],
                ]
            )
        out += [f"### {title} (n = {n})", "", md_table(["method", *CORE], rows), ""]
    # ---- preregistered hypotheses
    out += ["## Preregistered hypotheses (primary model: " + primary + ")", ""]
    hrows = []
    verdicts = {}
    for h, desc, sel, metric, fused, thr, op in [
        (
            "H1",
            "dev configuration: gold_coverage_packed, fused minus G >= +0.15",
            "dev:configuration",
            "gold_coverage_packed",
            "LGE",
            0.15,
            "ge",
        ),
        (
            "H2",
            "dev application_code: G minus fused <= 0.05 (fused - G >= -0.05)",
            "dev:application_code",
            "gold_coverage_packed",
            "LGE",
            -0.05,
            "ge",
        ),
        (
            "H3",
            "dev all: precision_packed, fused minus G >= 0",
            "dev",
            "precision_packed",
            "LGE",
            0.0,
            "ge",
        ),
        (
            "H3b",
            "45 queries: precision_packed, fused minus G >= 0 (supplementary)",
            "repos",
            "precision_packed",
            "LGE",
            0.0,
            "ge",
        ),
    ]:
        per_k = {}
        for k in (30, 60):
            d = data.diff(name(fused, primary, k), "RET-G", metric, sel)
            ok = d["mean_diff"] >= thr - 1e-12
            ci_ok = d["ci_lo"] >= thr
            per_k[k] = {"diff": d, "pass": ok, "ci_clears": ci_ok}
        holds = all(v["pass"] for v in per_k.values())
        verdicts[h] = holds
        hrows.append([h, desc, f"{data.mean('RET-G', metric, sel):.3f}", ci(per_k[30]["diff"]), "PASS" if per_k[30]["pass"] else "FAIL", ci(per_k[60]["diff"]), "PASS" if per_k[60]["pass"] else "FAIL",
                      ("PASS" if holds else "FAIL") + ("" if not holds or all(v["ci_clears"] for v in per_k.values()) else " (CI includes values below the threshold)")])  # fmt: skip
    # H4
    e, l = name("E", primary), "RET-L"
    d4 = data.diff(e, l, "mrr", "repos:exact_identifier")
    d4b = data.diff(e, l, "recall@5", "repos:exact_identifier")
    holds4 = d4["mean_diff"] < 0
    verdicts["H4"] = holds4
    hrows.append(["H4", "exact_identifier (n=10): MRR of E minus BM25 (RET-L) < 0", f"L={data.mean(l, 'mrr', 'repos:exact_identifier'):.3f}; E={data.mean(e, 'mrr', 'repos:exact_identifier'):.3f}", ci(d4), "PASS" if holds4 else "FAIL", f"recall@5 diff {ci(d4b)}", "-", "PASS" if holds4 else "FAIL"])  # fmt: skip
    out += [
        md_table(
            [
                "H",
                "test",
                "G / base mean",
                "diff k=30 [95% CI]",
                "k=30",
                "diff k=60 [95% CI]",
                "k=60",
                "holds (both k)",
            ],
            hrows,
        ),
        "",
    ]
    go = verdicts["H1"] and verdicts["H2"]
    out += [
        f"Decision rule (H1 and H2 on dev): **{'GO' if go else 'NO-GO'}** for the primary model `{primary}`.",
        "",
    ]
    res["verdicts"], res["go"] = verdicts, go

    # ---- same for the other models (supplementary)
    srows = []
    for tag in models:
        for fused in ("LGE", "LE"):
            for k in (30, 60):
                a = name(fused, tag, k)
                d1 = data.diff(a, "RET-G", "gold_coverage_packed", "dev:configuration")
                d2 = data.diff(a, "RET-G", "gold_coverage_packed", "dev:application_code")
                d3 = data.diff(a, "RET-G", "precision_packed", "dev")
                srows.append([tag, a, ci(d1), ci(d2), ci(d3)])
    out += ["## All models: fused minus G (supplementary; the verdict uses the primary model only)", "",
            md_table(["model", "arm", "H1 dev config coverage", "H2 dev app_code coverage", "H3 dev packed precision"], srows), ""]  # fmt: skip

    # ---- best hybrid (rule in the prereg)
    cand = [m for m in methods if (m.startswith("RET-LE@") or m.startswith("RET-LGE@"))]
    score = {m: 0.0 for m in cand}
    for sel in ("repos", "dev"):
        for metric in RANKMETRICS:
            vals = sorted({round(data.mean(m, metric, sel), 9) for m in cand}, reverse=True)
            for m in cand:
                score[m] += vals.index(round(data.mean(m, metric, sel), 9)) + 1
    prim = [m for m in cand if data.model_of[m] == primary]
    best = sorted(cand, key=lambda m: (score[m] / 8, data.mean(m, "tokens_used", "dev"), m))[0]
    best_prim = sorted(prim, key=lambda m: (score[m] / 8, data.mean(m, "tokens_used", "dev"), m))[0]
    res["best_hybrid_all_models"], res["best_hybrid_primary"] = best, best_prim
    out += ["## Best-performing hybrid (preregistered descriptive rule: mean rank over recall@10, mrr, ndcg@10, gold_coverage_packed on repos and dev; lower is better)", "",
            md_table(["arm", "model", "mean rank"], [[m, data.model_of[m], f"{score[m] / 8:.2f}"] for m in sorted(cand, key=lambda m: score[m])]), "",
            f"Best hybrid overall: `{best}`; best hybrid of the primary model: `{best_prim}`.", ""]  # fmt: skip

    # ---- direct comparisons
    primary_lge = name("LGE", primary, 60)
    arms = [
        ("RET-G", "RET-G (existing best)"),
        (primary_lge, "RET-LGE (G + embeddings, k=60)"),
        (e, "RET-E (embeddings alone)"),
        (best, "best hybrid"),
    ]
    out += ["## Direct comparisons (paired differences A - B, 95% bootstrap CI)", ""]
    pairs = [
        ("RET-G", primary_lge),
        (primary_lge, e),
        ("RET-G", e),
        (best, "RET-G"),
        (best, primary_lge),
        ("RET-L", "RET-G"),
        (e, "RET-L"),
    ]
    for sel, title in sels:
        rows = []
        for a, b in pairs:
            rows.append(
                [
                    f"{a} - {b}",
                    *[
                        ci(data.diff(a, b, m, sel))
                        for m in (
                            "recall@10",
                            "mrr",
                            "ndcg@10",
                            "file_hit@1",
                            "gold_coverage_packed",
                            "precision_packed",
                        )
                    ],
                ]
            )
        out += [
            f"### {title}",
            "",
            md_table(
                [
                    "A - B",
                    "recall@10",
                    "mrr",
                    "ndcg@10",
                    "file_hit@1",
                    "gold_cov_packed",
                    "precision_packed",
                ],
                rows,
            ),
            "",
        ]
    res["arms"] = [a for a, _ in arms]

    # ---- per type / class
    out += ["## Per query type (45 benchmark queries) and per cause class (dev)", ""]
    for kind, keys in (
        (
            "repos",
            [
                "exact_identifier",
                "paraphrased_bug",
                "symptom_no_identifier",
                "indirect_dependency",
                "configuration",
                "multi_file",
            ],
        ),
        ("dev", ["configuration", "application_code"]),
    ):
        rows = []
        for q in keys:
            sel = f"{kind}:{q}"
            n = len(data.keys(sel))
            for m in ["RET-L", "RET-G", e, name("LE", primary, 60), primary_lge]:
                rows.append(
                    [
                        q,
                        n,
                        m,
                        *[
                            fmt(data.mean(m, c, sel))
                            for c in (
                                "recall@5",
                                "recall@10",
                                "mrr",
                                "ndcg@10",
                                "file_hit@1",
                                "gold_coverage_packed",
                                "precision_packed",
                            )
                        ],
                    ]
                )
        out += [
            f"### {kind}",
            "",
            md_table(
                [
                    "type/class",
                    "n",
                    "method",
                    "recall@5",
                    "recall@10",
                    "mrr",
                    "ndcg@10",
                    "file_hit@1",
                    "gold_cov_packed",
                    "precision_packed",
                ],
                rows,
            ),
            "",
        ]

    # ---- null: more context
    if data.null:
        out += [
            "## 'Just more context' null: RET-L / RET-G / RET-LGE at a 1.5x budget (4500 tokens)",
            "",
        ]
        rows = []
        for sel, title in sels:
            ks = [k for k in data.keys(sel)]
            for m in sorted(data.null):
                v = lambda c, m=m, ks=ks: sum(data.null[m][k][c] for k in ks) / len(ks)  # noqa: E731
                rows.append(
                    [
                        title,
                        m,
                        f"{v('gold_coverage_packed'):.3f}",
                        f"{v('precision_packed'):.3f}",
                        f"{v('tokens_used'):.0f}",
                    ]
                )
        out += [
            md_table(
                ["slice", "method (budget 4500)", "gold_cov_packed", "precision_packed", "tokens"],
                rows,
            ),
            "",
        ]
    return "\n".join(out), res


def cost_tables(runs: dict[str, Path], index_root: Path | None) -> str:
    out = ["## Cost", ""]
    rows = []
    for tag, path in runs.items():
        for b in load_builds(path):
            if b["method"].startswith(("RET-E@", "RET-L@")) or b["method"] == f"RET-E@{tag}":
                rows.append(
                    [
                        tag,
                        b["suite"],
                        b["unit"],
                        b["chunks"],
                        b["index_build_s"],
                        b["storage_bytes"],
                    ]
                )
    out += ["Index-build per workload, as timed by the harness for RET-E (first dense arm of each repo triggers the cold sync; later arms find it built, so their `index_build_s` is ~0):", "",
            md_table(["model", "suite", "unit", "chunks", "index_build_s (RET-E)", "store bytes"], rows[:12] + (["..."] if len(rows) > 12 else [])), ""]  # fmt: skip
    if index_root and (index_root / "build_log.jsonl").is_file():
        recs = [
            json.loads(x) for x in (index_root / "build_log.jsonl").read_text("utf-8").splitlines()
        ]
        agg: dict[tuple, dict] = {}
        for r in recs:
            g = "dev" if r["ctx"].startswith("shop_api-") else r["ctx"]
            a = agg.setdefault(
                (r["model"], g),
                {
                    "n": 0,
                    "chunks": 0,
                    "embedded": 0,
                    "reused": 0,
                    "sync_s": 0.0,
                    "warm_s": 0.0,
                    "store": 0,
                    "mat": 0,
                    "rss": 0.0,
                    "dims": r["dims"],
                },
            )
            a["n"] += 1
            a["chunks"] += r["chunks"]
            a["embedded"] += r["sync"]["texts_embedded"]
            a["reused"] += r["sync"]["reused"]
            a["sync_s"] += r["sync_s"]
            a["warm_s"] += r["warm_resync_s"]
            a["store"] = max(a["store"], r["store_bytes"])
            a["mat"] = max(a["mat"], r["live_matrix_bytes"])
            a["rss"] = max(a["rss"], r["peak_rss_mb"] or 0)
        out += ["Cold / incremental sync from the index build log (`build_log.jsonl`; `dev` = 30-odd mutated trees of one lab synced into one namespace, so only changed chunks are embedded after the first):", "",
                md_table(["model", "group", "dims", "trees synced", "chunks", "texts embedded", "vectors reused", "sync s (total)", "warm resync s (total)", "store bytes (max)", "live matrix bytes (max)", "process peak RSS MB (max)"],
                         [[m, g, a["dims"], a["n"], a["chunks"], a["embedded"], a["reused"], f"{a['sync_s']:.1f}", f"{a['warm_s']:.3f}", a["store"], a["mat"], f"{a['rss']:.0f}"] for (m, g), a in sorted(agg.items())]), ""]  # fmt: skip
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True, help="tag=dir")
    ap.add_argument("--null4500", type=Path)
    ap.add_argument("--primary", default="jina")
    ap.add_argument("--index-root", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    runs = {s.split("=", 1)[0]: Path(s.split("=", 1)[1]) for s in a.runs}
    data = Data(runs, a.null4500)
    text, res = analyse(data, a.primary)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "analysis.md").write_text(
        text + "\n\n" + cost_tables(runs, a.index_root) + "\n", "utf-8"
    )
    (a.out / "analysis.json").write_text(json.dumps(res, indent=1, default=str), "utf-8")
    print(text.split("## Per query type")[0][-3500:])
    print(
        json.dumps(
            {
                k: res[k]
                for k in ("verdicts", "go", "best_hybrid_all_models", "best_hybrid_primary")
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
