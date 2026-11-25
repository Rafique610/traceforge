# ruff: noqa: E501
"""Apply the PREREGISTERED thresholds R1-R16 (docs/research/rootcause-impact-evaluation.md, section 4)
to results/analysis/rootcause-eval/{summary,cases}.json and write verdicts.json + summary.md.

    python -m traceforge.analysis.rootcause_verdicts [--dir results/analysis/rootcause-eval]

Pure post-processing: no analysis is re-run and no threshold is chosen here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT = REPO / "results" / "analysis" / "rootcause-eval"


def f(x, nd=3) -> str:
    return "n/a" if x is None else f"{x:.{nd}f}"


def verdicts(summary: dict, cases: dict) -> list[dict]:
    pools, ab, imp = summary["pools"], summary["abstention"], summary["impact"]
    rc = [c for c in cases["rootcause"] if not c.get("invalid")]
    out: list[dict] = []

    def add(rid, text, passed, detail):
        out.append({"id": rid, "threshold": text, "pass": bool(passed), "measured": detail})

    A, BC, D, G, ALL = (pools[k] for k in ("A", "B+C", "D", "G", "ABCD+G"))

    def ranks(fam, arm="RC-overlay"):
        return {c["id"]: c["arms"][arm]["rank"] for c in rc if c["family"] == fam}

    a_ranks = ranks("A")
    add("R1", "A: RC top1 >= G top1, RC MRR >= G MRR, gold in top 3 for both A cases",
        A["RC-overlay"]["top1"] >= A["G-distance"]["top1"] and A["RC-overlay"]["rr"] >= A["G-distance"]["rr"]
        and all(r is not None and r <= 3 for r in a_ranks.values()),
        {"RC_top1": A["RC-overlay"]["top1"], "G_top1": A["G-distance"]["top1"], "RC_mrr": A["RC-overlay"]["rr"],
         "G_mrr": A["G-distance"]["rr"], "RC_ranks": a_ranks})  # fmt: skip
    add("R2", "B+C: RC top5 >= G top5 + 0.125 and RC top5 >= 0.75",
        BC["RC-overlay"]["top5"] >= BC["G-distance"]["top5"] + 0.125 and BC["RC-overlay"]["top5"] >= 0.75,
        {"RC_top5": BC["RC-overlay"]["top5"], "G_top5": BC["G-distance"]["top5"],
         "diff_ci95": BC["diff_top5_RC_minus_G-distance"]["ci95"]})  # fmt: skip
    add("R3", "B+C: RC top5 >= BM25 top5", BC["RC-overlay"]["top5"] >= BC["BM25"]["top5"],
        {"RC_top5": BC["RC-overlay"]["top5"], "BM25_top5": BC["BM25"]["top5"],
         "diff_ci95": BC["diff_top5_RC_minus_BM25"]["ci95"]})  # fmt: skip
    add(
        "R4",
        "D: RC gold key in top 3 for >= 3/4",
        D["RC-overlay"]["top3"] >= 0.75,
        {
            "RC_top3": D["RC-overlay"]["top3"],
            "G_top3": D["G-distance"]["top3"],
            "BM25_top3": D["BM25"]["top3"],
        },
    )
    add("R5", "A,B,C,D,G at equal 600-token cap: RC dep recall >= G and RC dep precision >= G",
        ALL["RC-overlay"]["dep_recall"] >= ALL["G-distance"]["dep_recall"]
        and ALL["RC-overlay"]["dep_precision"] >= ALL["G-distance"]["dep_precision"],
        {"RC": [ALL["RC-overlay"]["dep_recall"], ALL["RC-overlay"]["dep_precision"]],
         "G": [ALL["G-distance"]["dep_recall"], ALL["G-distance"]["dep_precision"]],
         "BM25": [ALL["BM25"]["dep_recall"], ALL["BM25"]["dep_precision"]]})  # fmt: skip
    g_ranks = ranks("G")
    decoys = [c["arms"]["RC-overlay"]["decoys_in_top5"] for c in rc if c["family"] == "G"]
    add("R6", "G: gold in top 3 for both and mean decoys in top 5 <= 1.0",
        all(r is not None and r <= 3 for r in g_ranks.values()) and sum(decoys) / len(decoys) <= 1.0,
        {"RC_ranks": g_ranks, "mean_decoys_top5": sum(decoys) / len(decoys)})  # fmt: skip
    add(
        "R7",
        "H: abstains on both; false abstention on non-H <= 1",
        ab["H_abstained"] == ab["H_n"] == 2 and ab["false_abstain"] <= 1,
        ab,
    )
    io = imp["IMP-overlay"]
    add(
        "R8",
        "F: macro selection recall >= 0.90 and detection 5/5",
        io["sel_recall"] >= 0.9 and io["detected"] == 1.0,
        {"sel_recall": io["sel_recall"], "detected": io["detected"]},
    )
    add(
        "R9",
        "F: macro fraction of suite selected <= 0.75",
        io["frac_suite"] <= 0.75,
        {"frac_suite": io["frac_suite"]},
    )
    add(
        "R10",
        "F: macro direct-dependant recall >= 0.90 and affected-dependant recall >= 0.80",
        io["direct_recall"] >= 0.9 and io["dep_recall"] >= 0.8,
        {"direct_recall": io["direct_recall"], "dep_recall": io["dep_recall"]},
    )
    add(
        "R11",
        "F: macro impact-report precision >= 0.70",
        io["dep_precision"] >= 0.7,
        {"dep_precision": io["dep_precision"]},
    )
    add(
        "R12",
        "F: mean false-positive warnings per patch <= 1.0",
        io["fp_flags"] <= 1.0,
        {"fp_flags": io["fp_flags"]},
    )
    add("R13", "hidden isolation: 0 hidden-path strings in any report",
        all(imp[a]["hidden_leak"] == 0 for a in ("IMP-overlay", "IMP-graph")),
        {a: imp[a]["hidden_leak"] for a in ("IMP-overlay", "IMP-graph")})  # fmt: skip
    add(
        "R14",
        "determinism: two full runs identical",
        summary["deterministic_two_runs"],
        {"result_digest": summary["result_digest"]},
    )
    lat = summary["latency_ms"]
    add(
        "R15",
        "latency: RC median <= 2000 ms, max <= 5000 ms",
        lat["RC-overlay_median"] <= 2000 and lat["RC-overlay_max"] <= 5000,
        lat,
    )
    add(
        "R16",
        "(informational) IMP-overlay selection recall >= BM25-select at equal k",
        io["sel_recall"] >= imp["BM25-select"]["sel_recall"],
        {"IMP-overlay": io["sel_recall"], "BM25-select": imp["BM25-select"]["sel_recall"]},
    )
    return out


def go_no_go(v: list[dict]) -> dict:
    p = {x["id"]: x["pass"] for x in v}
    return {"S12": all(p[k] for k in ("R1", "R2", "R3", "R14")),
            "S15": all(p[k] for k in ("R8", "R10", "R13", "R14"))}  # fmt: skip


def markdown(summary: dict, cases: dict, v: list[dict], gng: dict) -> str:
    arms = ("RC-overlay", "RC-overlay+bm25", "G-distance", "BM25")
    L = [
        "# Root-cause / impact evaluation results (reduced P5-S16)\n",
        f"Deterministic across two full runs: **{summary['deterministic_two_runs']}**; "
        f"result digest `{summary['result_digest'][:16]}`; priors sha256 `{summary['priors_sha256'][:16]}`; "
        f"token cap {summary['token_cap']}, top-k {summary['top_k']}.\n",
        "## Preregistered thresholds\n",
        "| # | Threshold | Result | Measured |",
        "|---|---|---|---|",
    ]
    for x in v:
        L.append(
            f"| {x['id']} | {x['threshold']} | {'PASS' if x['pass'] else 'FAIL'} | `{json.dumps(x['measured'], sort_keys=True)}` |"
        )
    L += [
        "",
        f"Go/no-go by the preregistered rule: S12 **{'go' if gng['S12'] else 'no-go'}**, "
        f"S15 **{'go' if gng['S15'] else 'no-go'}**.\n",
        "## Root-cause ranking by family (mean over cases)\n",
        "| Family | n | Arm | top1 | top3 | top5 | MRR | dep recall | dep precision | tokens |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for fam, d in summary["rootcause_by_family"].items():
        for arm in arms:
            a = d[arm]
            L.append(
                f"| {fam} | {d['n']} | {arm} | {f(a['top1'])} | {f(a['top3'])} | {f(a['top5'])} | {f(a['rr'])} | "
                f"{f(a['dep_recall'])} | {f(a['dep_precision'])} | {f(a['packed_tokens'], 0)} |"
            )
    L += [
        "",
        "## Per case (rank of the first acceptable root cause; `-` = not in the top 20)\n",
        "| Case | RC-overlay | RC+bm25 | G-distance | BM25 | abstain |",
        "|---|---|---|---|---|---|",
    ]
    for c in cases["rootcause"]:
        if c.get("invalid"):
            continue
        r = lambda a, c=c: c["arms"][a]["rank"] or "-"  # noqa: E731
        L.append(
            f"| {c['id']} | {r('RC-overlay')} | {r('RC-overlay+bm25')} | {r('G-distance')} | {r('BM25')} | {c['abstain']} |"
        )
    L += [
        "",
        "## Change impact (family F, macro over 5 patches)\n",
        "| Arm | selection recall | suite fraction | detected | dep recall | direct recall | dep precision | FP flags/patch | report tokens |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for arm, a in summary["impact"].items():
        if isinstance(a, dict):
            L.append(
                f"| {arm} | {f(a.get('sel_recall'))} | {f(a.get('frac_suite'))} | {f(a.get('detected'))} | {f(a.get('dep_recall'))} | "
                f"{f(a.get('direct_recall'))} | {f(a.get('dep_precision'))} | {f(a.get('fp_flags'))} | {f(a.get('report_tokens'), 0)} |"
            )
    L += [
        "",
        f"Hand-predicted failing sets equal to the measured ones: {summary['impact']['prediction_matches']} of {summary['impact']['n']}.\n",
        "Small-n caveat: 23 hand-built cases from two toy projects; one case moves a family rate by 25-50 points. "
        "No superiority claim is made; thresholds were decided before the run on point estimates.\n",
    ]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=DEFAULT)
    a = ap.parse_args(argv)
    summary = json.loads((a.dir / "summary.json").read_text(encoding="utf-8"))
    cases = json.loads((a.dir / "cases.json").read_text(encoding="utf-8"))
    v = verdicts(summary, cases)
    gng = go_no_go(v)
    (a.dir / "verdicts.json").write_text(
        json.dumps({"verdicts": v, "go_no_go": gng}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (a.dir / "summary.md").write_text(
        markdown(summary, cases, v, gng), encoding="utf-8", newline="\n"
    )
    print(json.dumps({x["id"]: x["pass"] for x in v}), gng)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
