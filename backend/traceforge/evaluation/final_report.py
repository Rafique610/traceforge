# ruff: noqa: E501
"""Offline results tables and graphs for the FINAL controlled evaluation (EVALUATION ONLY).

No model calls, no Docker, no servers. Reads the saved artifacts of four run directories under
`--final-dir` (`final-axforge-{L0,G0,L1,G1}`; override with `--prefix` or `--run COND=DIR`) and the frozen
test manifest, reuses `diag_eval.score_case` / `patch_eval.score_case` for per-case scoring, and writes
tables (markdown + CSV), figures (PNG if matplotlib is installed, else plain SVG), results.json and
results.md. Gaps are never filled: a missing or unscorable cell is listed and shows as "n/a".

Design: 2x2 = retrieval arm {L, G} x feedback {F0, F1}; conditions L0, G0 (full runs), L1, G1 (patch stage
only, started from the saved L0/G0 diagnosis of the same replicate, so diagnosis metrics exist for L0/G0 only).
Usage: python -m traceforge.evaluation.final_report --manifest M --final-dir D --out-dir O [--replicates 0,1,2]
       [--controls FILE] [--historical-v4 PATH] [--selection FILE]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import statistics
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

from traceforge.evaluation import diag_eval, patch_eval

CONDS = ("L0", "G0", "L1", "G1")
FULL = ("L0", "G0")  # conditions that have their own diagnosis
OUTCOMES = ("TEST_VERIFIED_IN_LAB", "REJECTED", "UNVERIFIED", "NO_PATCH")
INSUFFICIENT = "insufficient_evidence"
_CASE_FILES = {
    "run_meta.json", "repair.json", "diagnosis.json", "symptom.json", "retrieval.json",
    "context_sent.json", "evidence_v5.json", "trace.json", "requests.jsonl", "baseline_visible.json",
}  # fmt: skip
HISTORICAL_LIMITS = (
    "v4 results are NOT comparable with this evaluation and are never pooled with it: the v4 runs used a "
    "different prompt (diagnose/patch prompt versions), a different pipeline (v4 vs v5 evidence view, "
    "symptom handling, tool policy and repair loop), a different use of the data split (v4 numbers were "
    "partly obtained while developing on dev/validation cases, whereas the final test split is frozen), and "
    "different model settings (model id, temperature, token limits, retries). Differences between the two "
    "sets cannot be attributed to the retrieval arm or to feedback."
)


# ----------------------------------------------------------------------------- loading


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


def _load_controls(path: Path | None) -> set[str]:
    if not path:
        return set()
    text = path.read_text("utf-8").strip()
    if text.startswith("["):
        return {str(x) for x in json.loads(text)}
    return {ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")}


def _score_cell(run: Path, cond: str, case: dict, rep: int, datasets: Path) -> dict:
    """Score one (condition, case, replicate) record through the shared helpers (they read replicate r0)."""
    cid = case["case_id"]
    src = run / "cases" / f"{cid}.r{rep}"
    rec = _read(run / "records" / f"{cid}.r{rep}.json")
    cell = {"cond": cond, "case": cid, "rep": rep, "record": rec, "diag": None, "patch": None,
            "meta": _read(src / "run_meta.json") or {}, "attempts": (_read(src / "repair.json") or {}).get("attempts") or [],
            "issues": []}  # fmt: skip
    if rec is None:
        return cell
    if not src.is_dir():
        cell["issues"].append("case directory missing")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "records").mkdir()
            shutil.copy(run / "records" / f"{cid}.r{rep}.json", t / "records" / f"{cid}.r0.json")
            d = t / "cases" / f"{cid}.r0"
            d.mkdir(parents=True)
            if src.is_dir():
                for f in src.iterdir():
                    if f.is_file() and (
                        f.name in _CASE_FILES or re.fullmatch(r"attempt\d+\.diff", f.name)
                    ):
                        shutil.copy(f, d / f.name)
            if not (d / "requests.jsonl").exists():
                (d / "requests.jsonl").write_text("", "utf-8")
            if cond in FULL:
                cell["diag"] = diag_eval.score_case(t, case, datasets)
            cell["patch"] = patch_eval.score_case(t, case, datasets)
    except Exception as e:  # noqa: BLE001 - a scoring failure is reported, never silently dropped
        cell["issues"].append(f"score_error: {type(e).__name__}: {e}")
    return cell


def collect(cases: dict[str, dict], final_dir: Path, reps: list[int] | None, prefix: str,
            overrides: dict[str, Path], datasets: Path) -> dict:  # fmt: skip
    runs = {c: overrides.get(c, final_dir / f"{prefix}{c}") for c in CONDS}
    present = {c: p.is_dir() for c, p in runs.items()}
    perr: Counter = Counter()  # (cond, case, rep) -> provider_error directories
    found: set[int] = set()
    for c, p in runs.items():
        if not present[c]:
            continue
        for d in (p / "cases").glob("*.provider_error.*") if (p / "cases").is_dir() else []:
            m = re.fullmatch(r"(.+)\.r(\d+)\.provider_error\..+", d.name)
            if m:
                perr[(c, m.group(1), int(m.group(2)))] += 1
        for f in (p / "records").glob("*.json") if (p / "records").is_dir() else []:
            m = re.fullmatch(r".+\.r(\d+)\.json", f.name)
            if m:
                found.add(int(m.group(1)))
    replicates = sorted(reps) if reps is not None else sorted(found)
    cells: dict = {}
    missing: list[dict] = []
    for c in CONDS:
        for cid, case in cases.items():
            for r in replicates:
                if not present[c]:
                    cells[(c, cid, r)] = None
                    missing.append(
                        {"cond": c, "case": cid, "rep": r, "reason": "run directory missing"}
                    )
                    continue
                cell = _score_cell(runs[c], c, case, r, datasets)
                if cell["record"] is None:
                    n = perr[(c, cid, r)]
                    cells[(c, cid, r)] = None
                    missing.append(
                        {
                            "cond": c,
                            "case": cid,
                            "rep": r,
                            "reason": f"no record (provider_error artifacts: {n})"
                            if n
                            else "no record",
                        }
                    )
                else:  # fmt: skip
                    cells[(c, cid, r)] = cell
    return {
        "runs": runs,
        "present": present,
        "replicates": replicates,
        "cells": cells,
        "missing": missing,
        "perr": perr,
    }


# ----------------------------------------------------------------------------- provenance


def provenance(data: dict) -> dict:
    per_run, vals = {}, defaultdict(set)
    for c, p in data["runs"].items():
        if not data["present"][c]:
            per_run[c] = None
            continue
        meta = _read(p / "meta.json") or {}
        cs = [x for (cc, _, _), x in data["cells"].items() if cc == c and x]
        fps = sorted(
            {(x["meta"].get("code_fingerprint") or {}).get("sha256") or "none" for x in cs}
        )
        tiers = sorted({str(x["meta"].get("tier")) for x in cs})
        pv = sorted({str(x["record"].get("pipeline_version")) for x in cs})
        prov = sorted(
            {str(x["record"].get("provider")) for x in cs}
            | ({str(meta["provider"])} if "provider" in meta else set())
        )
        models = sorted({str(x["record"].get("model_id")) for x in cs})
        ds = sorted({str(x["record"].get("dataset_sha256")) for x in cs})
        per_run[c] = {"run_id": meta.get("run_id", p.name), "dir": str(p), "code_fingerprints": fps, "tiers": tiers,
                      "pipeline_versions": pv, "providers": prov, "model_ids": models, "dataset_sha256": ds,
                      "prompt_hashes": sorted({str(x["record"].get("prompt_hash")) for x in cs}),
                      "replicates_present": sorted({x["rep"] for x in cs}), "n_records": len(cs)}  # fmt: skip
        for k, v in (
            ("code_fingerprint", fps),
            ("tier", tiers),
            ("pipeline_version", pv),
            ("provider", prov),
            ("model_id", models),
            ("dataset_sha256", ds),
        ):
            vals[k].update(v)
    mixed = {k: sorted(v) for k, v in vals.items() if len(v) > 1}
    return {"runs": per_run, "all_share_one_fingerprint": len(vals["code_fingerprint"]) <= 1,
            "mixed": mixed, "pool_ok": not mixed, "replicates": data["replicates"]}  # fmt: skip


# ----------------------------------------------------------------------------- metrics


def frac(k, n) -> str:
    return f"{k}/{n} ({100 * k / n:.0f}%)" if n else "n/a"


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def _median(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None


def diag_metrics(cells: list[dict]) -> dict:
    rs = [c["diag"] for c in cells if c["diag"]]
    ans = [r for r in rs if r["gold_class"] != INSUFFICIENT]
    rej = [r["rejected_calls"] for r in rs if r.get("rejected_calls") is not None]
    return {
        "n": len(rs), "class_correct": sum(r["correct_class"] for r in rs),
        "function_correct": sum(r["exact_function"] for r in rs),
        "file_correct": sum(r["correct_file"] for r in rs),
        "n_answerable": len(ans), "function_correct_answerable": sum(r["exact_function"] for r in ans),
        "abstained": sum(bool(r["abstained"]) for r in rs),
        "n_insufficient": len(rs) - len(ans),
        "abstain_correct": sum(bool(r["abstained"]) for r in rs if r["gold_class"] == INSUFFICIENT),
        "abstain_wrong": sum(bool(r["abstained"]) for r in ans),
        "unsupported_claims": sum(len(r["unsupported_claims"]) for r in rs),
        "tool_calls": sum(r["tool_calls"] for r in rs),
        "rejected_submissions": sum(rej), "rejected_known_n": len(rej),
    }  # fmt: skip


def patch_metrics(cells: list[dict], n_provider_errors: int = 0) -> dict:
    ps = [c["patch"] for c in cells if c["patch"]]
    n = len(ps)
    return {
        "n": n, "generated": sum(p["patch_generated"] for p in ps), "applied": sum(p["patch_applied"] for p in ps),
        "reproducer_passed": sum(p["reproducer_passed"] for p in ps), "visible_passed": sum(p["visible_passed"] for p in ps),
        "hidden_passed": sum(bool(p["hidden_passed"]) for p in ps), "fixed": sum(p["fixed"] for p in ps),
        "with_regressions": sum(bool(p["regressions_visible"]) for p in ps),
        "regression_known_n": sum(p["regressions_visible"] is not None for p in ps),
        "outcomes": {o: sum(p["outcome"] == o for p in ps) for o in OUTCOMES},
        "attempts_dist": dict(sorted(Counter(p["attempts"] for p in ps).items())),
        "tokens_in": sum(p["tokens_in"] for p in ps), "tokens_out": sum(p["tokens_out"] for p in ps),
        "tokens_in_mean": _mean([p["tokens_in"] for p in ps]), "tokens_out_mean": _mean([p["tokens_out"] for p in ps]),
        "latency_ms_mean": _mean([p["latency_ms"] for p in ps]), "latency_ms_median": _median([p["latency_ms"] for p in ps]),
        "model_s_mean": _mean([p["model_s"] for p in ps]), "model_s_known_n": sum(p["model_s"] is not None for p in ps),
        "provider_failures": n_provider_errors,
    }  # fmt: skip


def scopes(data: dict, pool_ok: bool) -> list[tuple[str, set[int]]]:
    out = [(f"r{r}", {r}) for r in data["replicates"]]
    if pool_ok and len(data["replicates"]) > 0:
        out.append(("pooled", set(data["replicates"])))
    return out


def select(data, cond, reps, pred=lambda case: True, cases=None):
    return [
        x
        for (c, cid, r), x in data["cells"].items()
        if c == cond and r in reps and x and cid in cases and pred(cases[cid])
    ]


def provider_failures(data, cond, reps, pred, cases):
    return sum(
        n
        for (c, cid, r), n in data["perr"].items()
        if c == cond and r in reps and cid in cases and pred(cases[cid])
    )


# ----------------------------------------------------------------------------- paired analysis


def _pair_keys(data, a, b, reps, primary):
    return [(cid, r) for r in sorted(reps) for cid in primary
            if data["cells"].get((a, cid, r)) and data["cells"].get((b, cid, r))]  # fmt: skip


def _unpaired(data, a, b, reps, primary, keys):
    return len(primary) * len(reps) - len(keys)


def _tab(pairs):
    both = sum(x and y for x, y in pairs)
    a = sum(x and not y for x, y in pairs)
    b = sum(y and not x for x, y in pairs)
    return {
        "n_pairs": len(pairs),
        "both": both,
        "a_only": a,
        "b_only": b,
        "neither": len(pairs) - both - a - b,
    }


def paired(data, reps, primary) -> dict:
    out: dict = {"L_vs_G": {}, "F0_vs_F1": {}}

    def fixed(c):
        return bool(c["patch"] and c["patch"]["fixed"])

    for name, (a, b), get in (
        ("diagnosis_function_correct_F0", ("L0", "G0"), lambda c: bool(c["diag"] and c["diag"]["exact_function"])),
        ("diagnosis_class_correct_F0", ("L0", "G0"), lambda c: bool(c["diag"] and c["diag"]["correct_class"])),
        ("fixed_F0", ("L0", "G0"), fixed),
        ("fixed_F1", ("L1", "G1"), fixed),
    ):  # fmt: skip
        keys = _pair_keys(data, a, b, reps, primary)
        res = _tab(
            [(get(data["cells"][(a, k, r)]), get(data["cells"][(b, k, r)])) for k, r in keys]
        )
        res["unpaired_excluded"] = _unpaired(data, a, b, reps, primary, keys)
        res["a_only_means"] = f"{a} only"
        out["L_vs_G"][name] = res
    for name, (a, b) in (("tokens_F0", ("L0", "G0")), ("tokens_F1", ("L1", "G1"))):
        keys = _pair_keys(data, a, b, reps, primary)
        d = [
            tot(data["cells"][(b, k, r)]) - tot(data["cells"][(a, k, r)])
            for k, r in keys
            if tot(data["cells"][(a, k, r)]) is not None
            and tot(data["cells"][(b, k, r)]) is not None
        ]
        out["L_vs_G"][name] = {"n_pairs": len(d), "G_less": sum(x < 0 for x in d), "G_more": sum(x > 0 for x in d), "equal": sum(x == 0 for x in d), "mean_G_minus_L": _mean(d), "unpaired_excluded": _unpaired(data, a, b, reps, primary, keys)}  # fmt: skip
    for arm in "LG":
        a, b = f"{arm}0", f"{arm}1"
        keys = _pair_keys(data, a, b, reps, primary)
        res = _tab(
            [(fixed(data["cells"][(a, k, r)]), fixed(data["cells"][(b, k, r)])) for k, r in keys]
        )
        res["unpaired_excluded"] = _unpaired(data, a, b, reps, primary, keys)
        out["F0_vs_F1"][f"fixed_arm{arm}"] = res
    return out


def tot(c):
    p = c["patch"]
    return None if not p else p["tokens_in"] + p["tokens_out"]


def _first_failed(c):
    at = c["attempts"]
    return None if not at else not at[0].get("visible_passed")


def _fixed_attempt(c):
    if c["patch"] and c["patch"]["fixed"] and c["attempts"]:
        return c["attempts"][-1]["n"]
    return None


def feedback_analysis(data, reps, primary) -> dict:
    """Feedback benefit = F0 first attempt failed AND F1 first attempt failed AND F1 verified at a later attempt
    (that attempt actually received feedback). `worse` = F0 verified but F1 not."""
    res = {"benefit": [], "fail_to_pass_without_feedback_evidence": [], "worse": [], "f1_failed_first_no_recovery": 0, "undetermined_no_attempt_data": 0, "pairs": 0}  # fmt: skip
    for arm in "LG":
        for cid, r in _pair_keys(data, f"{arm}0", f"{arm}1", reps, primary):
            c0, c1 = data["cells"][(f"{arm}0", cid, r)], data["cells"][(f"{arm}1", cid, r)]
            res["pairs"] += 1
            row = {"arm": arm, "case": cid, "rep": r, "f0_outcome": c0["record"]["outcome"], "f0_attempts": len(c0["attempts"]),
                   "f0_fixed_attempt": _fixed_attempt(c0), "f1_outcome": c1["record"]["outcome"], "f1_attempts": len(c1["attempts"]),
                   "f1_fixed_attempt": _fixed_attempt(c1)}  # fmt: skip
            if (c0["patch"] or {}).get("fixed") and not (c1["patch"] or {}).get("fixed"):
                res["worse"].append(row)
            f0f, f1f = _first_failed(c0), _first_failed(c1)
            if f0f is None or f1f is None:
                res["undetermined_no_attempt_data"] += 1
                continue
            fa = row["f1_fixed_attempt"]
            if f0f and f1f and fa and fa >= 2:
                passing = next((a for a in c1["attempts"] if a["n"] == fa), {})
                row["feedback_received_at_pass"] = bool(passing.get("feedback_received"))
                key = (
                    "benefit"
                    if row["feedback_received_at_pass"]
                    else "fail_to_pass_without_feedback_evidence"
                )
                res[key].append(row)
            elif f1f and not fa:
                res["f1_failed_first_no_recovery"] += 1
    return res


def noise(data, reps, primary) -> dict:
    out = {}
    for c in CONDS:
        fx, dg = defaultdict(list), defaultdict(list)
        for cid in primary:
            for r in sorted(reps):
                x = data["cells"].get((c, cid, r))
                if x and x["patch"]:
                    fx[cid].append(x["patch"]["fixed"])
                if x and x["diag"]:
                    dg[cid].append(x["diag"]["exact_function"])
        multi = [v for v in fx.values() if len(v) >= 2]
        dmulti = [v for v in dg.values() if len(v) >= 2]
        out[c] = {"cases_with_2plus_replicates": len(multi), "fixed_disagree": sum(len(set(v)) > 1 for v in multi),
                  "diag_cases_with_2plus": len(dmulti), "diag_disagree": sum(len(set(v)) > 1 for v in dmulti),
                  "per_replicate_fixed": {r: frac(sum(bool(x and x["patch"] and x["patch"]["fixed"]) for (cc, cid, rr), x in data["cells"].items() if cc == c and rr == r and cid in primary), sum(bool(x and x["patch"]) for (cc, cid, rr), x in data["cells"].items() if cc == c and rr == r and cid in primary)) for r in sorted(reps)}}  # fmt: skip
    return out


# ----------------------------------------------------------------------------- tables


class Tables:
    def __init__(self, out: Path):
        self.dir = out / "tables"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.md: list[str] = []
        self.index: dict[str, dict] = {}

    def add(self, name: str, title: str, headers: list[str], rows: list[list], note: str = ""):
        rows = [["n/a" if v is None else v for v in r] for r in rows]
        with (self.dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(headers)
            w.writerows(rows)
        lines = [f"### {title}", ""] + ([note, ""] if note else [])
        lines += ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
        lines += ["| " + " | ".join(str(v) for v in r) + " |" for r in rows]
        self.md.append("\n".join(lines) + "\n")
        self.index[name] = {
            "title": title,
            "csv": f"tables/{name}.csv",
            "headers": headers,
            "rows": rows,
        }


def build_tables(data, cases, primary_ids, controls, prov, tb: Tables):
    pool_ok = prov["pool_ok"]
    primary = {c: cases[c] for c in primary_ids}
    allp = lambda case: True  # noqa: E731
    sc = scopes(data, pool_ok)
    d_rows, p_rows, e_rows, metrics = [], [], [], {}
    for sname, reps in sc:
        for cond in CONDS:
            cs = select(data, cond, reps, allp, primary)
            pm = patch_metrics(cs, provider_failures(data, cond, reps, allp, primary))
            dm = diag_metrics(cs) if cond in FULL else None
            metrics[f"{sname}/{cond}"] = {"diagnosis": dm, "patch": pm}
            if dm:
                dn = dm["n"]
                d_rows.append([sname, cond, dn, frac(dm["class_correct"], dn), frac(dm["function_correct"], dn), frac(dm["function_correct_answerable"], dm["n_answerable"]), frac(dm["file_correct"], dn), frac(dm["abstained"], dn), f"{dm['abstain_correct']}/{dm['n_insufficient']} of insufficient_evidence; {dm['abstain_wrong']} wrong", dm["unsupported_claims"], dm["tool_calls"], f"{dm['rejected_submissions']} (known for {dm['rejected_known_n']}/{dn})"])  # fmt: skip
            n = pm["n"]
            p_rows.append([sname, cond, n, frac(pm["generated"], n), frac(pm["applied"], n), frac(pm["reproducer_passed"], n), frac(pm["visible_passed"], n), frac(pm["hidden_passed"], n), frac(pm["fixed"], n), f"{pm['with_regressions']} (known for {pm['regression_known_n']}/{n})", ", ".join(f"{o.replace('TEST_VERIFIED_IN_LAB', 'VERIFIED')}={v}" for o, v in pm["outcomes"].items())])  # fmt: skip
            e_rows.append([sname, cond, n, ", ".join(f"{k}:{v}" for k, v in pm["attempts_dist"].items()) or "n/a", pm["tokens_in_mean"], pm["tokens_out_mean"], pm["latency_ms_mean"], pm["latency_ms_median"], f"{pm['model_s_mean']} (n={pm['model_s_known_n']})" if pm["model_s_mean"] is not None else None, pm["provider_failures"]])  # fmt: skip
    note_pool = (
        ""
        if pool_ok
        else "POOLING REFUSED (mixed provenance, see Provenance); only per-replicate rows are shown."
    )
    tb.add("diagnosis_by_condition", "Diagnosis metrics (L0 and G0 only; L1/G1 share the L0/G0 diagnosis)", ["scope", "cond", "n case-runs", "class correct", "exact function/key", "exact fn/key (answerable only)", "file correct", "abstained", "correct abstentions", "unsupported claims", "tool calls", "rejected submissions"], d_rows, note_pool)  # fmt: skip
    tb.add("patch_by_condition", "Patch / repair metrics", ["scope", "cond", "n case-runs", "patch generated", "applied", "reproducer pass", "visible pass", "hidden pass", "fixed (TEST_VERIFIED)", "cases with visible regressions", "outcomes"], p_rows, "L1/G1 are patch-stage runs started from the shared L0/G0 diagnosis. " + note_pool)  # fmt: skip
    tb.add("effort_by_condition", "Attempts, tokens, latency, provider failures", ["scope", "cond", "n case-runs", "attempts distribution (attempts:count)", "mean tokens in", "mean tokens out", "mean latency_ms", "median latency_ms", "mean model_s", "provider_error artifacts"], e_rows, "Tokens/latency of L1/G1 cover the patch stage only. " + note_pool)  # fmt: skip

    if pool_ok:
        for key, label in (("cause_class", "cause class"), ("variant_group", "variant group")):
            rows = []
            for st in sorted({c[key] for c in primary.values()}):
                pred = lambda case, st=st, key=key: case[key] == st  # noqa: E731
                for cond in CONDS:
                    cs = select(data, cond, set(data["replicates"]), pred, primary)
                    pm = patch_metrics(cs)
                    dm = diag_metrics(cs) if cond in FULL else None
                    rows.append([st, sum(1 for c in primary.values() if pred(c)), cond, pm["n"], frac(dm["class_correct"], dm["n"]) if dm else "shared with " + cond[0] + "0", frac(dm["function_correct"], dm["n"]) if dm else "shared", frac(pm["fixed"], pm["n"])])  # fmt: skip
            tb.add(f"by_{key}", f"Per {label} (pooled over replicates)", [label, "cases", "cond", "n case-runs", "class correct", "exact function/key", "fixed"], rows)  # fmt: skip
        site_tables(data, primary, tb, metrics)
    return metrics


def site_tables(data, primary, tb: Tables, metrics):
    """Independent fault sites = variant_group (variants of one group are NOT independent)."""
    reps = set(data["replicates"])
    sites = defaultdict(list)
    for cid, c in primary.items():
        sites[c["variant_group"]].append(cid)
    rows, summ = [], {}
    for s, ids in sorted(sites.items()):
        row = [s, primary[ids[0]]["cause_class"], len(ids)]
        for cond in CONDS:
            cs = [
                x
                for (c, cid, r), x in data["cells"].items()
                if c == cond and r in reps and cid in ids and x and x["patch"]
            ]
            row.append(f"{sum(x['patch']['fixed'] for x in cs)}/{len(cs)}")
        rows.append(row)
    for cond in CONDS:
        n_s = fx_any = fx_all = dg_any = 0
        for ids in sites.values():
            cs = [
                x
                for (c, cid, r), x in data["cells"].items()
                if c == cond and r in reps and cid in ids and x and x["patch"]
            ]
            if not cs:
                continue
            n_s += 1
            fx_any += any(x["patch"]["fixed"] for x in cs)
            fx_all += all(x["patch"]["fixed"] for x in cs)
            dg_any += any(x["diag"]["exact_function"] for x in cs if x["diag"])
        summ[cond] = {"sites_with_records": n_s, "sites_any_fixed": fx_any, "sites_all_runs_fixed": fx_all, "sites_any_exact_function": dg_any if cond in FULL else None}  # fmt: skip
    metrics["sites"] = {
        "n_sites": len(sites),
        "cases_per_site": {s: len(i) for s, i in sites.items()},
        "by_condition": summ,
    }
    tb.add("sites", "Per independent fault site (variant_group): fixed case-runs / case-runs over all replicates", ["site", "cause_class", "cases in site", *[f"{c} fixed/runs" for c in CONDS]], rows, f"Unit of independence: {len(sites)} sites for {len(primary)} cases.")  # fmt: skip
    tb.add("sites_summary", "Site-level summary (a site counts once regardless of its variants)", ["cond", "sites with records", "sites with >=1 fixed run", "sites with all runs fixed", "sites with >=1 exact function/key"], [[c, v["sites_with_records"], v["sites_any_fixed"], v["sites_all_runs_fixed"], v["sites_any_exact_function"]] for c, v in summ.items()])  # fmt: skip


def paired_tables(pr, fb, nz, tb: Tables, label: str):
    rows = []
    for name, v in pr["L_vs_G"].items():
        if "both" in v:
            rows.append(
                [
                    name,
                    v["n_pairs"],
                    f"both={v['both']}, L only={v['a_only']}, G only={v['b_only']}, neither={v['neither']}",
                    v["unpaired_excluded"],
                ]
            )
        else:
            rows.append([name, v["n_pairs"], f"G fewer tokens={v['G_less']}, G more={v['G_more']}, equal={v['equal']}, mean(G-L)={v['mean_G_minus_L']}", v["unpaired_excluded"]])  # fmt: skip
    tb.add(f"paired_L_vs_G_{label}", f"Paired L vs G, same case/replicate ({label}; counts only)", ["measure", "paired case-runs", "counts", "unpaired excluded"], rows)  # fmt: skip
    rows = [[k, v["n_pairs"], f"both={v['both']}, F0 only={v['a_only']}, F1 only={v['b_only']}, neither={v['neither']}", v["unpaired_excluded"]] for k, v in pr["F0_vs_F1"].items()]  # fmt: skip
    tb.add(f"paired_F0_vs_F1_{label}", f"Paired F0 vs F1, same case/replicate/arm ({label}; counts only)", ["measure", "paired case-runs", "counts", "unpaired excluded"], rows)  # fmt: skip
    hdr = [
        "arm",
        "case",
        "rep",
        "F0 outcome",
        "F0 attempts",
        "F0 verified at",
        "F1 outcome",
        "F1 attempts",
        "F1 verified at",
    ]
    fmt = lambda r: [  # noqa: E731
        r["arm"],
        r["case"],
        r["rep"],
        r["f0_outcome"],
        r["f0_attempts"],
        r["f0_fixed_attempt"],
        r["f1_outcome"],
        r["f1_attempts"],
        r["f1_fixed_attempt"],
    ]
    tb.add(f"feedback_benefit_{label}", f"Feedback benefit: F0 first attempt failed; F1 first attempt failed, then verified at attempt>=2 with feedback received ({label}): {len(fb['benefit'])}", hdr, [fmt(r) for r in fb["benefit"]])  # fmt: skip
    tb.add(f"feedback_worse_{label}", f"F1 worse than F0 (F0 verified, F1 not) ({label}): {len(fb['worse'])}", hdr, [fmt(r) for r in fb["worse"]])  # fmt: skip
    if fb["fail_to_pass_without_feedback_evidence"]:
        tb.add(f"feedback_unattributed_{label}", f"F1 fail-to-pass where the passing attempt shows no feedback received (not counted as benefit) ({label}): {len(fb['fail_to_pass_without_feedback_evidence'])}", hdr, [fmt(r) for r in fb["fail_to_pass_without_feedback_evidence"]])  # fmt: skip
    tb.add(f"noise_{label}", f"Replicate-to-replicate disagreement ({label})", ["cond", "cases with >=2 replicates", "fixed outcome differs", "diag cases >=2 reps", "diag exact-function differs", "fixed per replicate"], [[c, v["cases_with_2plus_replicates"], v["fixed_disagree"], v["diag_cases_with_2plus"] if c in FULL else None, v["diag_disagree"] if c in FULL else None, "; ".join(f"r{r}: {x}" for r, x in v["per_replicate_fixed"].items())] for c, v in nz.items()])  # fmt: skip


# ----------------------------------------------------------------------------- charts (specs -> SVG or PNG)

PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#7F7F7F"]


def chart_specs(data, primary, metrics, reps_all) -> list[dict]:
    specs = []
    ro = reps_all
    conds_lbl, dots_diag, dots_fix, tok_vals, tok_dots = [], [], [], [], []
    diag_v, fix_v = [], []
    for cond in CONDS:
        src = "L0" if cond[0] == "L" else "G0"
        cs = select(data, cond, set(ro), lambda c: True, primary)
        dcs = select(data, src, set(ro), lambda c: True, primary)
        pm, dm = patch_metrics(cs), diag_metrics(dcs)
        conds_lbl.append(f"{cond} (n={pm['n']})")
        diag_v.append(dm["function_correct"] / dm["n"] if dm["n"] else None)
        fix_v.append(pm["fixed"] / pm["n"] if pm["n"] else None)
        dd, df, dt = [], [], []
        for r in ro:
            a, b = (
                patch_metrics(select(data, cond, {r}, lambda c: True, primary)),
                diag_metrics(select(data, src, {r}, lambda c: True, primary)),
            )
            df.append(a["fixed"] / a["n"] if a["n"] else None)
            dd.append(b["function_correct"] / b["n"] if b["n"] else None)
            dt.append((a["tokens_in_mean"] or 0) + (a["tokens_out_mean"] or 0) if a["n"] else None)
        dots_diag.append(dd)
        dots_fix.append(df)
        tok_vals.append(
            ((pm["tokens_in_mean"] or 0) + (pm["tokens_out_mean"] or 0)) if pm["n"] else None
        )
        tok_dots.append(dt)
    specs.append({"name": "diagnosis_vs_repair", "kind": "bars", "title": "Diagnosis (exact function/key; L1/G1 = shared L0/G0 diagnosis) vs repair (fixed), dots = replicates", "ylabel": "fraction of case-runs", "ymax": 1.0, "categories": conds_lbl, "series": [{"name": "diagnosis exact", "values": diag_v, "dots": dots_diag}, {"name": "fixed", "values": fix_v, "dots": dots_fix}]})  # fmt: skip
    specs.append({"name": "tokens_per_condition", "kind": "bars", "title": "Mean tokens (in+out) per case-run; L1/G1 = patch stage only; dots = replicates", "ylabel": "tokens", "ymax": None, "categories": conds_lbl, "series": [{"name": "mean tokens", "values": tok_vals, "dots": tok_dots}]})  # fmt: skip
    cats, series = [], {o: [] for o in OUTCOMES}
    for st in sorted({c["cause_class"] for c in primary.values()}):
        for cond in CONDS:
            cs = select(data, cond, set(ro), lambda c, st=st: c["cause_class"] == st, primary)
            pm = patch_metrics(cs)
            cats.append(f"{st} {cond} (n={pm['n']})")
            for o in OUTCOMES:
                series[o].append(pm["outcomes"][o] / pm["n"] if pm["n"] else 0)
    specs.append({"name": "outcomes_by_stratum", "kind": "stacked", "title": "Outcome mix per cause class and condition", "ylabel": "fraction of case-runs", "categories": cats, "series": [{"name": o, "values": v} for o, v in series.items()]})  # fmt: skip
    labels = ["attempt 1", "attempt 2", "attempt 3", "attempt >=4", "not fixed"]
    ser = []
    for cond in CONDS:
        cs = select(data, cond, set(ro), lambda c: True, primary)
        cnt = [0] * 5
        for c in cs:
            if not c["patch"]:
                continue
            fa = _fixed_attempt(c) if c["patch"]["fixed"] else None
            cnt[4 if fa is None else min(fa, 4) - 1] += 1
        ser.append({"name": f"{cond} (n={sum(cnt)})", "values": cnt, "dots": None})
    specs.append({"name": "feedback_attempt_progress", "kind": "bars", "title": "Attempt at which the case-run is verified (F0 = L0/G0, F1 = L1/G1)", "ylabel": "case-runs", "ymax": None, "categories": labels, "series": ser})  # fmt: skip
    lat = [
        [
            p["latency_ms"] / 1000
            for p in (c["patch"] for c in select(data, cond, set(ro), lambda c: True, primary))
            if p
        ]
        for cond in CONDS
    ]
    specs.append({"name": "latency_boxplot", "kind": "box", "title": "Record latency per case-run (L1/G1 = patch stage only)", "ylabel": "seconds", "categories": [f"{c} (n={len(v)})" for c, v in zip(CONDS, lat, strict=True)], "data": lat})  # fmt: skip
    return specs


def _svg_chart(spec: dict) -> str:  # noqa: C901
    W, H, L, R, T, B = 920, 500, 70, 20, 60, 130
    pw, ph = W - L - R, H - T - B
    kind, cats = spec["kind"], spec["categories"]
    if kind == "bars":
        vals = [v for s in spec["series"] for v in s["values"] if v is not None] + [d for s in spec["series"] if s.get("dots") for ds in s["dots"] for d in ds if d is not None]  # fmt: skip
        ymax = spec["ymax"] or (max(vals) * 1.1 if vals and max(vals) > 0 else 1)
    elif kind == "stacked":
        ymax = 1.0
    else:
        allv = [v for d in spec["data"] for v in d]
        ymax = max(allv) * 1.1 if allv else 1
    y = lambda v: T + ph - ph * v / ymax  # noqa: E731
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">', f'<rect width="{W}" height="{H}" fill="white"/>', f'<text x="{L}" y="24" font-size="14" font-weight="bold">{escape(spec["title"])}</text>']  # fmt: skip
    for i in range(6):
        v = ymax * i / 5
        o.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#ddd"/><text x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v:.2f}</text>' if ymax <= 5 else f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#ddd"/><text x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v:.0f}</text>')  # fmt: skip
    o.append(
        f'<text x="14" y="{T + ph / 2}" transform="rotate(-90 14 {T + ph / 2})" text-anchor="middle">{escape(spec["ylabel"])}</text>'
    )
    if not cats:
        o.append(f'<text x="{L}" y="{T + 20}">no data</text></svg>')
        return "\n".join(o)
    cw = pw / len(cats)
    rot = len(cats) > 6
    for i, c in enumerate(cats):
        cx = L + cw * (i + 0.5)
        ly = T + ph + 16
        o.append(f'<text x="{cx:.1f}" y="{ly}" text-anchor="{"end" if rot else "middle"}"' + (f' transform="rotate(-35 {cx:.1f} {ly})"' if rot else "") + f">{escape(c)}</text>")  # fmt: skip
    series = spec.get("series", [])
    if kind == "bars":
        k = len(series)
        bw = cw * 0.8 / k
        for si, s in enumerate(series):
            col = PALETTE[si % len(PALETTE)]
            for i, v in enumerate(s["values"]):
                x0 = L + cw * i + cw * 0.1 + bw * si
                if v is None:
                    o.append(
                        f'<text x="{x0 + bw / 2:.1f}" y="{y(0) - 4:.1f}" text-anchor="middle" fill="#888">n/a</text>'
                    )
                    continue
                o.append(
                    f'<rect x="{x0:.1f}" y="{y(v):.1f}" width="{bw:.1f}" height="{y(0) - y(v):.1f}" fill="{col}"/>'
                )
                o.append(f'<text x="{x0 + bw / 2:.1f}" y="{y(v) - 4:.1f}" text-anchor="middle" font-size="10">{v:.2f}</text>' if ymax <= 5 else f'<text x="{x0 + bw / 2:.1f}" y="{y(v) - 4:.1f}" text-anchor="middle" font-size="10">{v:.0f}</text>')  # fmt: skip
                for d in (s.get("dots") or [[]] * len(cats))[i]:
                    if d is not None:
                        o.append(
                            f'<circle cx="{x0 + bw / 2:.1f}" cy="{y(d):.1f}" r="3.5" fill="white" stroke="black"/>'
                        )
    elif kind == "stacked":
        for i in range(len(cats)):
            base = 0.0
            for si, s in enumerate(series):
                v = s["values"][i]
                o.append(f'<rect x="{L + cw * i + cw * 0.1:.1f}" y="{y(base + v):.1f}" width="{cw * 0.8:.1f}" height="{y(base) - y(base + v):.1f}" fill="{PALETTE[si % len(PALETTE)]}"/>')  # fmt: skip
                base += v
    else:
        for i, d in enumerate(spec["data"]):
            if not d:
                o.append(
                    f'<text x="{L + cw * (i + 0.5):.1f}" y="{y(0) - 4:.1f}" text-anchor="middle" fill="#888">n/a</text>'
                )
                continue
            q = statistics.quantiles(d, n=4, method="inclusive") if len(d) > 1 else [d[0]] * 3
            cx = L + cw * (i + 0.5)
            o.append(
                f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(min(d)):.1f}" y2="{y(max(d)):.1f}" stroke="black"/>'
            )
            o.append(f'<rect x="{cx - cw * 0.25:.1f}" y="{y(q[2]):.1f}" width="{cw * 0.5:.1f}" height="{max(y(q[0]) - y(q[2]), 1):.1f}" fill="{PALETTE[i % 8]}" fill-opacity="0.6" stroke="black"/>')  # fmt: skip
            o.append(f'<line x1="{cx - cw * 0.25:.1f}" x2="{cx + cw * 0.25:.1f}" y1="{y(q[1]):.1f}" y2="{y(q[1]):.1f}" stroke="black" stroke-width="2"/>')  # fmt: skip
    if kind != "box":
        for si, s in enumerate(series):
            lx = W - R - 170
            o.append(f'<rect x="{lx}" y="{34 + 16 * si}" width="10" height="10" fill="{PALETTE[si % len(PALETTE)]}"/><text x="{lx + 14}" y="{43 + 16 * si}" font-size="11">{escape(s["name"])}</text>')  # fmt: skip
    o.append("</svg>")
    return "\n".join(o)


def _mpl_chart(spec: dict, path: Path) -> bool:
    try:
        import matplotlib  # noqa: PLC0415

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: PLC0415
    except ImportError:
        return False
    fig, ax = plt.subplots(figsize=(10, 5.5))
    cats, kind = spec["categories"], spec["kind"]
    xs = list(range(len(cats)))
    if kind == "box":
        ax.boxplot([d or [float("nan")] for d in spec["data"]], tick_labels=cats)
    elif kind == "stacked":
        base = [0.0] * len(cats)
        for s in spec["series"]:
            ax.bar(xs, s["values"], bottom=base, label=s["name"])
            base = [b + v for b, v in zip(base, s["values"], strict=True)]
    else:
        k = len(spec["series"])
        w = 0.8 / k
        for si, s in enumerate(spec["series"]):
            pos = [x + w * si - 0.4 + w / 2 for x in xs]
            ax.bar(pos, [v or 0 for v in s["values"]], w, label=s["name"])
            for p, ds in zip(pos, s.get("dots") or [[]] * len(xs), strict=True):
                ax.scatter(
                    [p] * len(ds), [d for d in ds], c="white", edgecolors="black", zorder=3, s=18
                )
    if kind != "box":
        ax.set_xticks(
            xs, cats, rotation=35 if len(cats) > 6 else 0, ha="right" if len(cats) > 6 else "center"
        )
        ax.legend(fontsize=8)
    ax.set_title(spec["title"], fontsize=10)
    ax.set_ylabel(spec["ylabel"])
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return True


def write_charts(specs: list[dict], out: Path) -> list[str]:
    fdir = out / "figures"
    fdir.mkdir(parents=True, exist_ok=True)
    files = []
    for s in specs:
        png = fdir / f"{s['name']}.png"
        try:
            if _mpl_chart(s, png):
                files.append(f"figures/{png.name}")
                continue
        except Exception:  # noqa: BLE001 - fall back to the dependency-free SVG
            pass
        svg = fdir / f"{s['name']}.svg"
        svg.write_text(_svg_chart(s), "utf-8")
        files.append(f"figures/{svg.name}")
    return files


# ----------------------------------------------------------------------------- historical v4


def historical_section(path: Path | None = None) -> dict:
    """Limitations text only; with a path, lists the historical records separately (never pooled)."""
    out = {"limitations": HISTORICAL_LIMITS, "pooled": False, "records": []}
    if path and path.exists():
        files = [path] if path.is_file() else sorted(path.rglob("*.json"))
        for f in files:
            d = _read(f)
            if isinstance(d, dict) and "case_id" in d:
                out["records"].append({"file": f.name, "case_id": d.get("case_id"), "condition": d.get("condition"), "outcome": d.get("outcome"), "pipeline_version": d.get("pipeline_version")})  # fmt: skip
    return out


# ----------------------------------------------------------------------------- orchestration


def run_report(manifest: Path, final_dir: Path, out_dir: Path, replicates: list[int] | None = None,
               controls: Path | None = None, prefix: str = "final-axforge-",
               overrides: dict[str, Path] | None = None, historical: Path | None = None, selection: Path | None = None) -> dict:  # fmt: skip
    cases = {c["case_id"]: c for c in json.loads(manifest.read_text("utf-8"))}
    n_manifest = len(cases)
    if selection:
        wanted = json.loads(selection.read_text("utf-8"))["cases"]
        cases = {c: cases[c] for c in wanted if c in cases}
    datasets = manifest.resolve().parents[1]
    out_dir.mkdir(parents=True, exist_ok=True)
    data = collect(cases, final_dir, replicates, prefix, overrides or {}, datasets)
    prov = provenance(data)
    ctrl = _load_controls(controls) & set(cases)
    unknown_ctrl = sorted(_load_controls(controls) - set(cases))
    primary_ids = [c for c in cases if c not in ctrl]
    primary = {c: cases[c] for c in primary_ids}
    tb = Tables(out_dir)
    metrics = build_tables(data, cases, primary_ids, ctrl, prov, tb)
    reps = set(data["replicates"])
    pr = paired(data, reps, primary_ids)
    fb = feedback_analysis(data, reps, primary_ids)
    nz = noise(data, reps, primary_ids)
    per_rep = {}
    if prov["pool_ok"]:
        paired_tables(pr, fb, nz, tb, "pooled")
    else:
        for r in data["replicates"]:
            pr_r, fb_r, nz_r = (
                paired(data, {r}, primary_ids),
                feedback_analysis(data, {r}, primary_ids),
                noise(data, {r}, primary_ids),
            )
            paired_tables(pr_r, fb_r, nz_r, tb, f"r{r}")
            per_rep[f"r{r}"] = {"paired": pr_r, "feedback": fb_r}
    ctrl_metrics = {}
    if ctrl:
        rows = []
        for cond in CONDS:
            cs = [x for (c, cid, r), x in data["cells"].items() if c == cond and cid in ctrl and x]
            pm, dm = patch_metrics(cs), diag_metrics(cs) if cond in FULL else None
            ctrl_metrics[cond] = {"patch": pm, "diagnosis": dm}
            rows.append(
                [
                    cond,
                    pm["n"],
                    frac(pm["fixed"], pm["n"]),
                    frac(dm["class_correct"], dm["n"]) if dm else "shared",
                ]
            )
        tb.add("controls", "Controls (excluded from every primary denominator)", ["cond", "n control case-runs", "fixed", "class correct"], rows)  # fmt: skip
    specs = chart_specs(data, primary, metrics, data["replicates"]) if prov["pool_ok"] else []
    figures = write_charts(specs, out_dir)
    issues = [
        {"cond": c, "case": cid, "rep": r, "issues": x["issues"]}
        for (c, cid, r), x in data["cells"].items()
        if x and x["issues"]
    ]
    shared_mismatch = []
    for arm in "LG":
        for cid, r in _pair_keys(data, f"{arm}0", f"{arm}1", reps, primary_ids):
            d0, d1 = (
                data["cells"][(f"{arm}0", cid, r)]["record"]["diagnosis"],
                data["cells"][(f"{arm}1", cid, r)]["record"]["diagnosis"],
            )
            if (d0.get("cause_class"), d0.get("target")) != (
                d1.get("cause_class"),
                d1.get("target"),
            ):
                shared_mismatch.append({"arm": arm, "case": cid, "rep": r})
    results = {
        "denominators": {"manifest_cases": n_manifest, "selected_cases": len(cases) if selection else None, "primary_cases": len(primary_ids), "control_cases": sorted(ctrl), "unknown_control_ids": unknown_ctrl, "replicates": data["replicates"], "expected_case_runs_per_condition": len(primary_ids) * len(data["replicates"]), "case_runs_present": {c: sum(1 for (cc, cid, _), x in data["cells"].items() if cc == c and x and cid in primary) for c in CONDS}},  # fmt: skip
        "provenance": prov, "metrics": metrics, "paired": pr if prov["pool_ok"] else per_rep, "feedback": fb if prov["pool_ok"] else None,
        "noise": nz if prov["pool_ok"] else None, "controls": ctrl_metrics, "missing_cells": data["missing"], "scoring_issues": issues,
        "diagnosis_not_shared_between_F0_and_F1": shared_mismatch, "figures": figures, "tables": {k: v["csv"] for k, v in tb.index.items()},
        "historical_v4": historical_section(historical),
    }  # fmt: skip
    (out_dir / "results.json").write_text(json.dumps(results, indent=1, default=str), "utf-8")
    (out_dir / "results.md").write_text(render_md(results, tb), "utf-8")
    return results


def render_md(res: dict, tb: Tables) -> str:
    d, prov = res["denominators"], res["provenance"]
    o = ["# Final evaluation results", "", "## Denominators", ""]
    if d.get("selected_cases") is not None:
        o.append(
            f"**selected subset ({d['selected_cases']} cases of {d['manifest_cases']}), reduced protocol**"
        )
    o += [f"- manifest cases: {d['manifest_cases']}; primary (non-control) cases: {d['primary_cases']}; control cases: {len(d['control_cases'])} (reported separately)",
          f"- replicates: {d['replicates']}; expected case-runs per condition: {d['expected_case_runs_per_condition']}",
          "- case-runs present per condition: " + ", ".join(f"{c}={n}" for c, n in d["case_runs_present"].items()),
          "- Rates are k/n over case-runs with a record; missing cells are NOT counted as failures or successes (see Missing)."]  # fmt: skip
    if d["unknown_control_ids"]:
        o.append(f"- control ids not in the manifest (ignored): {d['unknown_control_ids']}")
    o += ["", "## Provenance", ""]
    for c, p in prov["runs"].items():
        if p is None:
            o.append(f"- {c}: run directory MISSING")
        else:
            o.append(f"- {c}: run `{p['run_id']}`, replicates {p['replicates_present']}, records {p['n_records']}, tier {p['tiers']}, pipeline {p['pipeline_versions']}, provider {p['providers']}, model {p['model_ids']}, fingerprint {[f[:12] for f in p['code_fingerprints']]}")  # fmt: skip
    o.append(f"- all records share one code fingerprint: {prov['all_share_one_fingerprint']}")
    if prov["mixed"]:
        o += ["", "**POOLING REFUSED: mixed provenance.** " + "; ".join(f"{k}: {v}" for k, v in prov["mixed"].items()) + ". Pooled tables, strata, sites and graphs are omitted; only per-replicate tables are given.", ""]  # fmt: skip
    if res["diagnosis_not_shared_between_F0_and_F1"]:
        o.append(f"- WARNING: {len(res['diagnosis_not_shared_between_F0_and_F1'])} F1 records whose diagnosis differs from the F0 run of the same replicate: {res['diagnosis_not_shared_between_F0_and_F1']}")  # fmt: skip
    o += ["", "## Missing / incomplete cells", ""]
    if not res["missing_cells"] and not res["scoring_issues"]:
        o.append("None.")
    for m in res["missing_cells"]:
        o.append(f"- {m['cond']} {m['case']} r{m['rep']}: n/a ({m['reason']})")
    for s in res["scoring_issues"]:
        o.append(f"- {s['cond']} {s['case']} r{s['rep']}: {'; '.join(s['issues'])}")
    o += [
        "",
        "## Tables",
        "",
        "Diagnosis and repair metrics are separate tables. Counts only; no significance claims.",
        "",
    ]
    o += tb.md
    if res["figures"]:
        o += ["## Figures", ""] + [f"![{Path(f).stem}]({f})" for f in res["figures"]] + [""]
    h = res["historical_v4"]
    o += ["## Historical v4 comparison", "", h["limitations"], ""]
    if h["records"]:
        o += ["Historical records (listed separately, not pooled):", ""] + [
            f"- {r['case_id']} {r['condition']}: {r['outcome']} ({r['pipeline_version']})"
            for r in h["records"]
        ]
    return "\n".join(o) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--final-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--replicates", help="comma list, e.g. 0,1,2 (default: discovered)")
    ap.add_argument("--controls", type=Path, help="file of control case ids (lines or JSON list)")
    ap.add_argument("--prefix", default="final-axforge-")
    ap.add_argument("--run", action="append", default=[], help="COND=DIR override (repeatable)")
    ap.add_argument("--historical-v4", type=Path)
    ap.add_argument(
        "--selection", type=Path, help='JSON with a "cases" list: frozen subset of the manifest'
    )
    a = ap.parse_args(argv)
    reps = [int(x) for x in a.replicates.split(",")] if a.replicates else None
    ov = {s.partition("=")[0]: Path(s.partition("=")[2]) for s in a.run}
    res = run_report(
        a.manifest,
        a.final_dir,
        a.out_dir,
        reps,
        a.controls,
        a.prefix,
        ov,
        a.historical_v4,
        a.selection,
    )
    print(
        f"wrote {a.out_dir / 'results.md'} (pool_ok={res['provenance']['pool_ok']}, missing={len(res['missing_cells'])})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
