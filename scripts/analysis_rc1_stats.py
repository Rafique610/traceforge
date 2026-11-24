"""Zero-token statistics over the existing RC1 final records (read-only; no provider calls).

Reads results/final/final-axforge-{L0,G0,L1,G1}/records/*.json and datasets/manifests/test.json,
writes results/analysis/rc1-paired-stats/{rc1_stats.json,rc1_stats.md}.
Run: backend/.venv/Scripts/python.exe scripts/analysis_rc1_stats.py
"""

import glob
import json
import math
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from traceforge.evaluation.metrics.common import gold_targets  # noqa: E402
from traceforge.contracts.case_manifest import CaseManifest  # noqa: E402

OUT = ROOT / "results/analysis/rc1-paired-stats"
COMBINED_CEILING = 4_800_000


def wilson(k, n, z=1.959964):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def exact_p(b, c):
    """Two-sided exact McNemar = binomial test of b vs c discordant pairs at p=0.5."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n)


def load():
    man = {
        r["case_id"]: CaseManifest.model_validate(r)
        for r in json.load(open(ROOT / "datasets/manifests/test.json"))
    }
    R = defaultdict(dict)
    for c in ("L0", "G0", "L1", "G1"):
        for f in glob.glob(str(ROOT / f"results/final/final-axforge-{c}/records/*.json")):
            r = json.load(open(f))
            R[c][(r["case_id"], r["replicate"])] = r
    return man, R


def measures(man, r, case):
    m = man[case]
    d = r["diagnosis"]
    return {
        "fixed": int(r["outcome"] == "TEST_VERIFIED_IN_LAB"),
        "cause_correct": int(d["cause_class"] == m.cause_class),
        "exact_target": int(not d["abstained"] and d["target"] in gold_targets(m)),
    }


def paired(a, b, vals, metric):
    """vals[cond][case] -> dict. Counts for b relative to a."""
    cases = sorted(set(vals[a]) & set(vals[b]))
    x = [vals[a][c][metric] for c in cases]
    y = [vals[b][c][metric] for c in cases]
    both = sum(i and j for i, j in zip(x, y))
    a_only = sum(i and not j for i, j in zip(x, y))
    b_only = sum(j and not i for i, j in zip(x, y))
    neither = len(cases) - both - a_only - b_only
    n = len(cases)
    return {
        "n": n, "metric": metric, "A": a, "B": b,
        "A_k": sum(x), "A_wilson95": wilson(sum(x), n),
        "B_k": sum(y), "B_wilson95": wilson(sum(y), n),
        "both": both, "A_only": a_only, "B_only": b_only, "neither": neither,
        "discordant": a_only + b_only,
        "exact_mcnemar_p_two_sided": exact_p(a_only, b_only),
    }  # fmt: skip


def main():
    man, R = load()
    r0 = {c: {k[0]: v for k, v in R[c].items() if k[1] == 0} for c in R}
    sites = sorted(r0["L0"])
    assert len(sites) == 35
    vals = {c: {k: measures(man, v, k) for k, v in r0[c].items()} for c in r0}
    groups = {man[s].variant_group for s in sites}
    out = {"n_sites": len(sites), "n_variant_groups_in_sample": len(groups),
           "replicate": 0, "cause_class_of_sites": {}, "per_condition": {}, "paired": []}  # fmt: skip
    for s in sites:
        k = man[s].cause_class
        out["cause_class_of_sites"][k] = out["cause_class_of_sites"].get(k, 0) + 1
    for c in ("L0", "G0", "L1", "G1"):
        for mt in ("fixed", "cause_correct", "exact_target"):
            k = sum(vals[c][s][mt] for s in sites)
            out["per_condition"][f"{c}.{mt}"] = {"k": k, "n": 35, "wilson95": wilson(k, 35)}
    for a, b in (("L0", "G0"), ("L1", "G1"), ("L0", "L1"), ("G0", "G1")):
        for mt in ("fixed", "cause_correct", "exact_target"):
            if mt != "fixed" and (a, b) in (("L0", "L1"), ("G0", "G1"), ("L1", "G1")):
                continue  # patch stage shares the diagnosis of F0
            out["paired"].append(paired(a, b, vals, mt))
    # replicate noise: sites with >=2 replicates
    noise = {}
    for c in ("L0", "G0", "L1", "G1"):
        byc = defaultdict(list)
        for (case, rep), r in R[c].items():
            byc[case].append((rep, measures(man, r, case)))
        multi = {k: sorted(v) for k, v in byc.items() if len(v) >= 2}
        per_rep = {}
        for rep in (0, 1, 2):
            cs = [k for k, v in multi.items() if any(x[0] == rep for x in v)]
            per_rep[f"r{rep}"] = {"sites": len(cs), "fixed": sum(
                dict(multi[k])[rep]["fixed"] for k in cs)}  # fmt: skip
        diff_fixed = [k for k, v in multi.items() if len({x[1]["fixed"] for x in v}) > 1]
        diff_exact = [k for k, v in multi.items() if len({x[1]["exact_target"] for x in v}) > 1]
        noise[c] = {"sites_with_replicates": len(multi),
                    "sites_with_r1": sum(any(x[0] == 1 for x in v) for v in multi.values()),
                    "sites_with_r2": sum(any(x[0] == 2 for x in v) for v in multi.values()),
                    "per_replicate_fixed_on_those_sites": per_rep,
                    "sites_fixed_outcome_differs_across_replicates": len(diff_fixed),
                    "sites_exact_target_differs_across_replicates": len(diff_exact),
                    "differing_fixed_sites": diff_fixed}  # fmt: skip
    out["replicate_noise"] = noise
    # replicate-matched L vs G on the replicate level (all 55 case-runs, NOT independent)
    allvals = {c: {k: measures(man, v, k[0]) for k, v in R[c].items()} for c in R}
    out["pooled_55_caseruns_L0_vs_G0_fixed_not_independent"] = paired("L0", "G0", allvals, "fixed")
    # cost
    cost = {}
    for c in ("L0", "G0", "L1", "G1"):
        for scope, recs in (("r0_35", [r0[c][s] for s in sites]), ("all_55", list(R[c].values()))):
            v = [r["tokens_in"] + r["tokens_out"] for r in recs]
            cost[f"{c}.{scope}"] = {"n": len(v), "sum": sum(v), "mean": st.mean(v),
                                    "median": st.median(v),
                                    "p90": sorted(v)[math.ceil(0.9 * len(v)) - 1],
                                    "max": max(v)}  # fmt: skip
    out["record_tokens"] = cost
    # ledger
    led = {}
    for slot, f in (("1", "runs/axforge_usage.jsonl"), ("2", "runs/axforge_usage_k2.jsonl")):
        rows = [json.loads(x) for x in open(ROOT / f) if x.strip()]
        rep = sum(int(x.get("total_tokens") or 0) for x in rows if x.get("type") == "request")
        est = sum(int(x.get("estimated_tokens") or 0) for x in rows if x.get("type") == "error")
        led[slot] = {"requests": sum(x.get("type") == "request" for x in rows),
                     "reported": rep, "error_estimated": est, "committed": rep + est}  # fmt: skip
    committed = led["1"]["committed"] + led["2"]["committed"]
    remaining = COMBINED_CEILING - committed
    led["combined_committed"] = committed
    led["combined_ceiling"] = COMBINED_CEILING
    led["combined_remaining"] = remaining
    out["ledger"] = led
    # budget: per-site cost = L0+G0 diagnosis + L1+G1 patch stages (mean / p90 of per-site sums)
    persite = [sum(r0[c][s]["tokens_in"] + r0[c][s]["tokens_out"] for c in r0) for s in sites]
    persite_diag = [sum(r0[c][s]["tokens_in"] + r0[c][s]["tokens_out"] for c in ("L0", "G0"))
                    for s in sites]  # fmt: skip
    p90 = sorted(persite)[math.ceil(0.9 * 35) - 1]
    out["budget"] = {
        "per_site_4_conditions_mean": st.mean(persite), "per_site_median": st.median(persite),
        "per_site_p90": p90, "per_site_L0G0_mean": st.mean(persite_diag),
        "max_extra_sites_at_mean": int(remaining // st.mean(persite)),
        "max_extra_sites_at_median": int(remaining // st.median(persite)),
        "max_extra_sites_at_p90": int(remaining // p90),
        "needed_for_50": 15, "tokens_needed_for_15_at_mean": 15 * st.mean(persite),
        "note": "estimate from record tokens (in+out); excludes retries, 429/error "
        "estimates (ledger overhead) and any safety margin",
    }  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rc1_stats.json").write_text(json.dumps(out, indent=1, default=list), "utf-8")
    L = [f"# RC1 paired statistics (35 sites, replicate 0)\n"]
    L.append("| comparison | metric | A k/n | B k/n | A only | B only | discordant | exact p |")
    L.append("|---|---|---|---|---|---|---|---|")
    for p in out["paired"]:
        L.append(f"| {p['A']} vs {p['B']} | {p['metric']} | {p['A_k']}/{p['n']} | "
                 f"{p['B_k']}/{p['n']} | {p['A_only']} | {p['B_only']} | {p['discordant']} | "
                 f"{p['exact_mcnemar_p_two_sided']:.3f} |")  # fmt: skip
    (OUT / "rc1_stats.md").write_text("\n".join(L) + "\n", "utf-8")
    print(json.dumps({k: out[k] for k in ("per_condition", "replicate_noise", "ledger", "budget")},
                     indent=1, default=list))
    for p in out["paired"]:
        print(p)


if __name__ == "__main__":
    main()
