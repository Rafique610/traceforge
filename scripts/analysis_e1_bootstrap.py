"""Zero-token paired/cluster bootstrap over a saved E1 run (retrieval, no LLM) + rules baseline.

Inputs : results/analysis/e1-test-all151/e1/<run_id>/bundles/{L,G,...}/<case>.json (from
         `python -m traceforge.retrieval.e1`), evidence bundles in .../evidence, datasets/manifests/test.json.
Outputs: results/analysis/e1-test-all151/{e1_bootstrap.json,e1_bootstrap.md,rules_baseline.json}
Seed   : 20261125 (python random.Random), 10,000 resamples, percentile 95% intervals.
Gold is used only for scoring; retrieval never sees it.
Run: backend/.venv/Scripts/python.exe scripts/analysis_e1_bootstrap.py [run_id]
"""

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from analysis_rc1_stats import exact_p, wilson  # noqa: E402
from traceforge.contracts.case_manifest import CaseManifest  # noqa: E402
from traceforge.contracts.context import ContextBundle  # noqa: E402
from traceforge.contracts.evidence import EvidenceBundle  # noqa: E402
from traceforge.evaluation.baselines.rules import baseline_records  # noqa: E402
from traceforge.evaluation.metrics.common import gold_node_ids, gold_targets  # noqa: E402
from traceforge.evaluation.metrics.retrieval import case_retrieval  # noqa: E402

BASE = ROOT / "results/analysis/e1-test-all151"
SEED, ITERS = 20261125, 10_000
METRICS = ("recall@1", "recall@5", "recall@10", "mrr", "ndcg@10")


def per_case(b, gold):
    s = case_retrieval(b, gold)
    return {"recall@1": s["found@1"] / s["gold"], "recall@5": s["found@5"] / s["gold"],
            "recall@10": s["found@10"] / s["gold"], "mrr": s["rr"], "ndcg@10": s["ndcg@10"]}  # fmt: skip


def pct(xs, q):
    return xs[min(int(q * len(xs)), len(xs) - 1)]


def boot_mean(vals, groups, clustered, rng):
    """vals: list of per-case numbers; groups: parallel list of group ids."""
    n = len(vals)
    if not clustered:
        ms = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(ITERS))
    else:
        by = defaultdict(list)
        for v, g in zip(vals, groups):
            by[g].append(v)
        keys = sorted(by)
        sums = {k: sum(by[k]) for k in keys}
        cnt = {k: len(by[k]) for k in keys}
        ms = []
        for _ in range(ITERS):
            pick = [keys[rng.randrange(len(keys))] for _ in keys]
            ms.append(sum(sums[k] for k in pick) / sum(cnt[k] for k in pick))
        ms.sort()
    return (pct(ms, 0.025), pct(ms, 0.975))


def summarize(vals, groups, seed_tag):
    n = len(vals)
    mean = sum(vals) / n
    return {"n_cases": n, "n_groups": len(set(groups)), "mean": mean,
            "ci_case": boot_mean(vals, groups, False, random.Random(f"{SEED}-{seed_tag}-case")),
            "ci_cluster": boot_mean(vals, groups, True, random.Random(f"{SEED}-{seed_tag}-grp"))}  # fmt: skip


def main():
    run_id = sys.argv[1] if len(sys.argv) > 1 else "e1-test-all151"
    ev_sub = sys.argv[2] if len(sys.argv) > 2 else "evidence"  # evidence dir used for rules baseline
    run = BASE / "e1" / run_id
    man = {r["case_id"]: CaseManifest.model_validate(r)
           for r in json.load(open(ROOT / "datasets/manifests/test.json"))}  # fmt: skip
    res = json.load(open(run / "result.json"))
    scored = sorted({c["case_id"] for c in res["cases"]})
    B = {}
    for meth in ("R0", "trace_only", "L", "G"):
        for cid in scored:
            B[(meth, cid)] = ContextBundle.model_validate(
                json.load(open(run / "bundles" / meth / f"{cid}.json"))["bundle"])
    M = {meth: {cid: per_case(B[(meth, cid)], gold_node_ids(man[cid])) for cid in scored}
         for meth in ("R0", "trace_only", "L", "G")}  # fmt: skip
    out = {"seed": SEED, "iterations": ITERS, "e1_run": run_id,
           "dataset_sha256": res["dataset_sha256"], "n_manifest": res["n_cases_in_manifest"],
           "n_scored": res["n_scored"], "n_groups_scored": len({man[c].variant_group for c in scored}),
           "skipped_reasons": sorted({s["reason"] for s in res["skipped"]}),
           "n_skipped": len(res["skipped"]), "methods": {}, "G_minus_L": {}}  # fmt: skip
    strata = {"all": scored}
    for cc in sorted({man[c].cause_class for c in scored}):
        strata[cc] = [c for c in scored if man[c].cause_class == cc]
    for s, cs in strata.items():
        grp = [man[c].variant_group for c in cs]
        out["methods"][s] = {}
        for meth in ("R0", "trace_only", "L", "G"):
            out["methods"][s][meth] = {
                mt: summarize([M[meth][c][mt] for c in cs], grp, f"{s}-{meth}-{mt}")
                for mt in METRICS}  # fmt: skip
        out["G_minus_L"][s] = {}
        for mt in METRICS:
            d = [M["G"][c][mt] - M["L"][c][mt] for c in cs]
            r = summarize(d, grp, f"{s}-d-{mt}")
            r["G_better"] = sum(x > 1e-12 for x in d)
            r["L_better"] = sum(x < -1e-12 for x in d)
            r["ties"] = len(d) - r["G_better"] - r["L_better"]
            r["exact_sign_p"] = exact_p(r["G_better"], r["L_better"])
            out["G_minus_L"][s][mt] = r
    # rules baseline on ALL manifest cases (diagnosis only; no LLM)
    ev = {}
    for cid in man:
        ev[cid] = EvidenceBundle.model_validate_json((BASE / ev_sub / f"{cid}.json").read_text("utf-8"))
    recs = baseline_records(ev, [man[c] for c in sorted(man)], res["dataset_sha256"])
    rb = {"n": len(recs), "n_groups": len({m.variant_group for m in man.values()}), "strata": {}}
    rows = []
    for r in recs:
        m = man[r.case_id]
        d = r.diagnosis
        rows.append({"case_id": r.case_id, "group": m.variant_group, "cause_class": m.cause_class,
                     "pred": d.cause_class, "target": d.target, "abstained": d.abstained,
                     "cause_correct": int(d.cause_class == m.cause_class),
                     "exact_target": int(bool(gold_targets(m)) and not d.abstained
                                         and d.target in gold_targets(m)),
                     "has_gold_target": int(bool(gold_targets(m)))})  # fmt: skip
    for s in ["all", *sorted({r["cause_class"] for r in rows})]:
        sub = [r for r in rows if s == "all" or r["cause_class"] == s]
        g = [r["group"] for r in sub]
        e = {"n": len(sub), "n_groups": len(set(g))}
        for mt in ("cause_correct",):
            v = [r[mt] for r in sub]
            e[mt] = {"k": sum(v), "wilson95_case": wilson(sum(v), len(v)),
                     "ci_cluster": boot_mean(v, g, True, random.Random(f"{SEED}-rules-{s}-{mt}"))}  # fmt: skip
        sg = [r for r in sub if r["has_gold_target"]]
        if sg:
            v = [r["exact_target"] for r in sg]
            gg = [r["group"] for r in sg]
            e["exact_target_on_cases_with_gold_target"] = {
                "k": sum(v), "n": len(v), "wilson95_case": wilson(sum(v), len(v)),
                "ci_cluster": boot_mean(v, gg, True, random.Random(f"{SEED}-rules-{s}-ex"))}  # fmt: skip
        rb["strata"][s] = e
    rb["predicted_distribution"] = {}
    for r in rows:
        k = f"{r['cause_class']} -> {r['pred']}"
        rb["predicted_distribution"][k] = rb["predicted_distribution"].get(k, 0) + 1
    rb["rows"] = rows
    (BASE / f"rules_baseline_{ev_sub}.json").write_text(json.dumps(rb, indent=1), "utf-8")
    (BASE / f"e1_bootstrap_{run_id}.json").write_text(json.dumps(out, indent=1), "utf-8")
    f = lambda x: f"{x:.3f}"  # noqa: E731
    L = [f"# E1 test-all151 bootstrap (seed {SEED}, {ITERS} resamples)\n",
         f"scored {out['n_scored']}/{out['n_manifest']} cases in {out['n_groups_scored']} groups\n",
         "| stratum | metric | L | G | G-L | case CI | cluster CI | G better/L better/tie | sign p |",
         "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for s in strata:
        for mt in METRICS:
            d = out["G_minus_L"][s][mt]
            L.append(f"| {s} (n={d['n_cases']}) | {mt} | {f(out['methods'][s]['L'][mt]['mean'])} | "
                     f"{f(out['methods'][s]['G'][mt]['mean'])} | {d['mean']:+.3f} | "
                     f"[{d['ci_case'][0]:+.3f}, {d['ci_case'][1]:+.3f}] | "
                     f"[{d['ci_cluster'][0]:+.3f}, {d['ci_cluster'][1]:+.3f}] | "
                     f"{d['G_better']}/{d['L_better']}/{d['ties']} | {d['exact_sign_p']:.3g} |")  # fmt: skip
    (BASE / f"e1_bootstrap_{run_id}.md").write_text("\n".join(L) + "\n", "utf-8")
    print("\n".join(L))
    print(json.dumps({k: v for k, v in rb.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
