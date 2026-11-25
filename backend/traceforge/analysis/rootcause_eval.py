# ruff: noqa: E501
"""Reduced P5-S16 evaluation: root-cause ranking and change impact on hand-labelled fixtures.

    python -m traceforge.analysis.rootcause_eval --out results/analysis/rootcause-eval

Zero provider calls. Expected relationships come from benchmarks/rootcause/cases (hand-written,
never from this tool). True test failures are obtained by REALLY running each fixture's pytest.
Thresholds are preregistered in docs/research/rootcause-impact-evaluation.md before this runs.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from rank_bm25 import BM25Okapi

from traceforge.analysis import priors as P
from traceforge.analysis.impact_report import make_provider
from traceforge.analysis.overlay import RuntimeFacts, build_overlay
from traceforge.analysis.ranker import (
    CANDIDATE_KINDS,
    RankerConfig,
    Seed,
    _expand_test_seeds,
    rank_root_causes,
    seeds_from_runtime,
)
from traceforge.codeintel import approx_tokens, build_graph, weighted_distances
from traceforge.regression.impact import GraphImpactProvider
from traceforge.regression.selection import select_tests

REPO = Path(__file__).resolve().parents[3]
CASES_DIR = REPO / "benchmarks" / "rootcause" / "cases"
TOKEN_CAP = 600  # equal token cap for the dependency recall/precision comparison
TOP_K = 20
BOOT_N, BOOT_SEED = 10_000, 20261125
HIDDEN = ["tests_hidden"]
ARMS = ("RC-overlay", "RC-overlay+bm25", "G-distance", "BM25")


# ---- running fixtures for real -------------------------------------------------------------
def materialise(src: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="rcfix_"))
    shutil.copytree(
        src, tmp / "repo", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache")
    )
    return tmp / "repo"


def run_pytest(root: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=root, capture_output=True, text=True, timeout=300, env=env,
    )  # fmt: skip
    return p.stdout + p.stderr


def collect_ids(root: Path) -> list[str]:
    out = run_pytest(root, "--collect-only", "tests")
    return [
        ln.strip().replace("\\", "/")
        for ln in out.splitlines()
        if "::" in ln and ln.startswith("tests")
    ]


_FRAME = re.compile(r"^(\S+\.py):(\d+): in (\S+)", re.M)
_SUMMARY = re.compile(r"^(FAILED|ERROR) (\S+?)(?: - .*)?$", re.M)
_SECTION = re.compile(r"^_{3,} (.+?) _{3,}$", re.M)


_ADDR = re.compile(r"0x[0-9a-fA-F]+")
_TMP = re.compile(r"\S*rcfix_\w+\S*")


def normalise_symptom(text: str) -> str:
    """Drop run-specific noise (memory addresses, random temp directory names) from the pytest
    section used as symptom text: they differ per run and would leak into BM25 tokens."""
    return _TMP.sub(" ", _ADDR.sub(" ", text))


def parse_pytest(out: str) -> dict:
    failed = sorted({m.group(2).replace("\\", "/") for m in _SUMMARY.finditer(out)})
    sections: dict[str, dict] = {}
    marks = list(_SECTION.finditer(out))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(out)
        body = out[m.end() : end]
        body = body.split("\n=====", 1)[0]
        frames = [(f.group(1).replace("\\", "/"), int(f.group(2))) for f in _FRAME.finditer(body)]
        sections[m.group(1).strip()] = {"frames": frames, "text": body.strip()}
    return {"failed": failed, "sections": sections, "tail": out[-400:]}


# ---- refs and packing ----------------------------------------------------------------------
def node_of(g, ref: str) -> str | None:
    if ref.startswith("cfg:"):
        return ref if ref in g else None
    for pre in ("func", "class"):
        nid = f"{pre}:{ref}"
        if nid in g:
            return nid
    return None


def node_cost(og, nid: str) -> int:
    d = og.node(nid)
    path, start, end = d.get("path"), d.get("start") or 1, d.get("end") or 1
    try:
        lines = (og.base.repo / path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 12
    return 12 + approx_tokens("\n".join(lines[start - 1 : min(end, start + 23)]))


def pack(og, ranked: Sequence[str], cap: int = TOKEN_CAP) -> tuple[list[str], int]:
    used, out = 0, []
    for n in ranked:
        c = node_cost(og, n)
        if used + c <= cap:
            used += c
            out.append(n)
    return out, used


# ---- baselines -----------------------------------------------------------------------------
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    for ident in re.findall(r"[A-Za-z0-9_]+", text):
        parts = [p.lower() for piece in ident.split("_") if piece for p in _CAMEL.findall(piece)]
        out += [p for p in parts if len(p) > 1]
        if len(parts) > 1:
            out.append(ident.lower())
    return out


def chunk_text(og, nid: str) -> str:
    d = og.node(nid)
    path, start, end = d.get("path") or "", d.get("start") or 1, d.get("end") or 1
    try:
        lines = (og.base.repo / path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    body = "\n".join(lines[start - 1 : end])
    return f"{path} {d.get('qualname') or d.get('name', '')} {d.get('name', '')}\n{body}"


def universe(og, kinds: Sequence[str] = CANDIDATE_KINDS) -> list[str]:
    return sorted(n for n, d in og.nx.nodes(data=True) if d["kind"] in kinds)


def rank_bm25(og, query: str, top_k: int = TOP_K, kinds: Sequence[str] = CANDIDATE_KINDS):
    ids = universe(og, kinds)
    docs = [tokenize(chunk_text(og, n)) or ["_"] for n in ids]
    if not ids:
        return []
    scores = BM25Okapi(docs).get_scores(list(dict.fromkeys(tokenize(query))))
    order = sorted(zip(ids, scores, strict=True), key=lambda t: (-round(float(t[1]), 9), t[0]))
    return [n for n, s in order[:top_k] if s > 0]


def rank_graph_distance(g, og, seeds: Sequence[Seed], top_k: int = TOP_K, max_cost: float = 15.0):
    """G-style: Dijkstra over the ORIGINAL graph (hub-penalised, weight x confidence), no overlay,
    no evidence classes, no direction priors, no per-hop budget. Same seeds as the ranker."""
    best: dict[str, float] = {}
    for s in _expand_test_seeds(og, list(seeds)):
        if s.node not in g:
            continue
        for n, c in weighted_distances(g, s.node, max_cost).items():
            total = c + (1.0 - s.relevance)
            if n not in best or total < best[n]:
                best[n] = total
    cand = [(c, n) for n, c in best.items() if g.node(n)["kind"] in CANDIDATE_KINDS]
    return [n for c, n in sorted(cand, key=lambda t: (round(t[0], 9), t[1]))[:top_k]]


# ---- metrics -------------------------------------------------------------------------------
def first_rank(ranked: Sequence[str], gold: set[str]) -> int | None:
    for i, n in enumerate(ranked, 1):
        if n in gold:
            return i
    return None


def file_rank(og, ranked: Sequence[str], files: set[str]) -> int | None:
    for i, n in enumerate(ranked, 1):
        if og.path_of(n) in files:
            return i
    return None


def rc_metrics(rank: int | None) -> dict:
    return {"rank": rank, "top1": int(rank == 1), "top3": int(bool(rank and rank <= 3)),
            "top5": int(bool(rank and rank <= 5)), "rr": (1.0 / rank) if rank else 0.0}  # fmt: skip


def boot_ci(diffs: Sequence[float]) -> tuple[float, float]:
    rng = random.Random(BOOT_SEED)
    n = len(diffs)
    if n == 0:
        return (float("nan"), float("nan"))
    means = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(BOOT_N))
    return (means[int(0.025 * BOOT_N)], means[int(0.975 * BOOT_N) - 1])


# ---- per-case runners ----------------------------------------------------------------------
def load_cases(cases_dir: Path = CASES_DIR) -> list[dict]:
    cases = [json.loads((p / "case.json").read_text(encoding="utf-8"))
             for p in sorted(cases_dir.iterdir()) if (p / "case.json").is_file()]  # fmt: skip
    for c in cases:
        c["_dir"] = str(cases_dir / c["id"])
    return cases


def run_rootcause_case(case: dict) -> dict:
    root = materialise(Path(case["_dir"]) / "repo")
    try:
        out = run_pytest(root, "--tb=short", "-rfE", "tests")
        parsed = parse_pytest(out)
        primary = case["primary_test"]
        title = primary.split("::")[-1]
        sec = parsed["sections"].get(title)
        if primary not in parsed["failed"] or sec is None:
            return {"id": case["id"], "family": case["family"], "invalid": True,
                    "why": "primary test did not fail", "tail": parsed["tail"]}  # fmt: skip
        frames, symptom = sec["frames"], normalise_symptom(sec["text"])
        t0 = time.perf_counter()
        g = build_graph(root, "fixture", cache_dir=None)
        og = build_overlay(
            g, RuntimeFacts(frames=frames, failing_tests=[primary]), hidden_paths=HIDDEN
        )
        seeds = seeds_from_runtime(og, frames, [primary], symptom)
        res = rank_root_causes(og, seeds, RankerConfig(top_k=TOP_K))
        t_rc = time.perf_counter() - t0
        gold = {n for r in case["gold"] if (n := node_of(og, r))}
        gold_files = set(case["gold_files"])
        exp = {n for r in [*case["chain"], *case.get("extra_deps", []), *case["gold"]]
               if (n := node_of(og, r))}  # fmt: skip
        decoys = {n for r in case.get("decoys", []) if (n := node_of(og, r))}
        # arms
        t0 = time.perf_counter()
        bm = rank_bm25(og, symptom)
        t_bm = time.perf_counter() - t0
        t0 = time.perf_counter()
        gd = rank_graph_distance(g, og, seeds)
        t_gd = time.perf_counter() - t0
        bm_seeds = [Seed(n, "retrieval", P.SEED_PRIOR["retrieval"] * (1.0 - 0.1 * i), False, "bm25")
                    for i, n in enumerate(bm[:3])]  # fmt: skip
        res2 = rank_root_causes(og, [*seeds, *bm_seeds], RankerConfig(top_k=TOP_K))
        ranked = {"RC-overlay": res.ids(), "RC-overlay+bm25": res2.ids(), "G-distance": gd,
                  "BM25": bm}  # fmt: skip
        rows = {}
        for arm, ids in ranked.items():
            packed, used = pack(og, ids)
            hit = len(set(packed) & exp)
            rows[arm] = {
                **rc_metrics(first_rank(ids, gold)),
                "file_rank": file_rank(og, ids, gold_files),
                "dep_recall": hit / len(exp) if exp else 0.0,
                "dep_precision": hit / len(packed) if packed else 0.0,
                "packed_tokens": used, "packed_n": len(packed),
                "decoys_in_top5": len(set(ids[:5]) & decoys),
                "top10": ids[:10],
            }  # fmt: skip
        return {
            "id": case["id"],
            "family": case["family"],
            "invalid": False,
            "abstain": res.abstain,
            "abstain_expected": bool(case.get("abstain_expected")),
            "unresolved": list(res.unresolved),
            "n_seeds": len(seeds),
            "ms": {"RC-overlay": t_rc * 1000, "BM25": t_bm * 1000, "G-distance": t_gd * 1000},
            "arms": rows,
            "top1_reasons": list(res.candidates[0].reasons) if res.candidates else [],
            "top1_evidence": res.candidates[0].evidence if res.candidates else None,
            "evidence_of_gold": next((c.evidence for c in res.candidates if c.node in gold), None),
            "frames": frames,
        }
    finally:
        shutil.rmtree(root.parent, ignore_errors=True)


def _norm_ref(x: str) -> str:
    return x[5:] if x.startswith("func:") or x.startswith("test:") else x


def _flag_keys(report) -> set[str]:
    return {f"{f.code}:{_norm_ref(f.subject)}" for f in report.risk_flags}


def run_impact_case(case: dict) -> dict:
    base = materialise(Path(case["_dir"]) / "base")
    patched = materialise(Path(case["_dir"]) / "patched")
    try:
        ids = collect_ids(base)
        base_out = parse_pytest(run_pytest(base, "--tb=line", "-rfE", "tests"))
        if base_out["failed"]:
            return {"id": case["id"], "family": "F", "invalid": True, "why": "base suite not green"}
        pat = parse_pytest(run_pytest(patched, "--tb=line", "-rfE", "tests"))
        true_failing: set[str] = set()
        for f in pat["failed"]:
            if f in ids:
                true_failing.add(f)
            else:  # collection error on a file: every test of that file fails
                true_failing |= {i for i in ids if i.split("::")[0] == f.split("::")[0]}
        suite = len(ids)
        out: dict = {"id": case["id"], "family": "F", "invalid": False, "suite": suite,
                     "true_failing": sorted(true_failing),
                     "predicted_failing": sorted(case["predicted_failing"]),
                     "prediction_matches": sorted(true_failing) == sorted(case["predicted_failing"])}  # fmt: skip
        exp_dep = {r for r in case["expected_dependants"]}
        exp_dir = {r for r in case["expected_direct"]}
        exp_flags = set(case["expected_flags"])

        def ref(nid: str) -> str:
            return _norm_ref(nid)

        arms: dict[str, dict] = {}
        for name, prov in (("IMP-overlay", make_provider()), ("IMP-graph", GraphImpactProvider())):
            t0 = time.perf_counter()
            rep = prov.analyse(base, patched, visible_tests=ids, hidden_paths=HIDDEN)
            dt = time.perf_counter() - t0
            sel = select_tests(rep, ids)
            chosen = set(sel.ids)
            reported = {ref(d.id) for d in [*rep.direct_dependants, *rep.transitive_dependants]}
            reported_direct = {ref(d.id) for d in rep.direct_dependants}
            fl = _flag_keys(rep)
            arms[name] = {
                "selected": sorted(chosen),
                "fallback": sel.fallback,
                "sel_recall": (len(chosen & true_failing) / len(true_failing))
                if true_failing
                else None,
                "frac_suite": len(chosen) / suite,
                "detected": int(bool(chosen & true_failing)),
                "dep_recall": len(reported & exp_dep) / len(exp_dep) if exp_dep else None,
                "direct_recall": len(reported_direct & exp_dir) / len(exp_dir) if exp_dir else None,
                "dep_precision": len(reported & exp_dep) / len(reported) if reported else None,
                "n_reported": len(reported),
                "flags": sorted(fl),
                "fp_flags": len(fl - exp_flags),
                "flag_recall": len(fl & exp_flags) / len(exp_flags) if exp_flags else None,
                "n_not_analysable": len(rep.not_analysable),
                "report_tokens": approx_tokens(rep.canonical_json()),
                "ms": dt * 1000,
                "sha": rep.impact_sha256,
                "hidden_leak": int(
                    any("tests_hidden" in x for x in rep.canonical_json().split('"'))
                ),
            }
        # plain BM25 over test chunks, selecting as many tests as IMP-overlay (equal k)
        g = build_graph(base, "base", cache_dir=None)
        og = build_overlay(g)
        tests = sorted(n for n, d in og.nx.nodes(data=True) if d["kind"] == "test" and n[5:] in ids)
        diff = []
        for rel in sorted(set(_changed_files(base, patched))):
            a = (
                (base / rel).read_text(encoding="utf-8").splitlines()
                if (base / rel).exists()
                else []
            )
            b = (
                (patched / rel).read_text(encoding="utf-8").splitlines()
                if (patched / rel).exists()
                else []
            )
            diff += [ln[1:] for ln in difflib.unified_diff(a, b, lineterm="", n=0)
                     if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]  # fmt: skip
        k = len(arms["IMP-overlay"]["selected"])
        docs = [tokenize(chunk_text(og, t)) or ["_"] for t in tests]
        sc = (
            BM25Okapi(docs).get_scores(list(dict.fromkeys(tokenize("\n".join(diff)))))
            if tests
            else []
        )
        order = sorted(zip(tests, sc, strict=True), key=lambda t: (-round(float(t[1]), 9), t[0]))
        chosen = {t[5:] for t, _ in order[:k]}
        arms["BM25-select"] = {
            "selected": sorted(chosen), "sel_recall": len(chosen & true_failing) / len(true_failing)
            if true_failing else None, "frac_suite": len(chosen) / suite,
            "detected": int(bool(chosen & true_failing)),
        }  # fmt: skip
        arms["full-suite"] = {"selected": ids, "sel_recall": 1.0 if true_failing else None,
                              "frac_suite": 1.0, "detected": int(bool(true_failing))}  # fmt: skip
        out["arms"] = arms
        return out
    finally:
        shutil.rmtree(base.parent, ignore_errors=True)
        shutil.rmtree(patched.parent, ignore_errors=True)


def _changed_files(a: Path, b: Path) -> list[str]:
    out = []
    for root in (a, b):
        for p in sorted(root.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                rel = p.relative_to(root).as_posix()
                x, y = a / rel, b / rel
                if not (x.exists() and y.exists() and x.read_bytes() == y.read_bytes()):
                    out.append(rel)
    return out


# ---- aggregation ---------------------------------------------------------------------------
def mean(xs: Sequence[float | None]) -> float | None:
    v = [x for x in xs if x is not None]
    return sum(v) / len(v) if v else None


def aggregate(rc: list[dict], imp: list[dict]) -> dict:
    ok = [r for r in rc if not r.get("invalid")]
    agg: dict = {
        "n_cases": len(rc) + len(imp),
        "n_invalid": sum(1 for r in rc + imp if r.get("invalid")),
    }
    fams = sorted({r["family"] for r in ok})
    by_fam: dict = {}
    for fam in fams:
        rs = [r for r in ok if r["family"] == fam]
        by_fam[fam] = {"n": len(rs)}
        for arm in ARMS:
            by_fam[fam][arm] = {k: mean([r["arms"][arm][k] for r in rs])
                                for k in ("top1", "top3", "top5", "rr", "dep_recall", "dep_precision",
                                          "packed_tokens", "decoys_in_top5")}  # fmt: skip
    agg["rootcause_by_family"] = by_fam
    pools = {"B+C": [r for r in ok if r["family"] in "BC"], "A": [r for r in ok if r["family"] == "A"],
             "D": [r for r in ok if r["family"] == "D"], "G": [r for r in ok if r["family"] == "G"],
             "ABCD+G": [r for r in ok if r["family"] in "ABCDG"]}  # fmt: skip
    agg["pools"] = {}
    for name, rs in pools.items():
        d: dict = {"n": len(rs)}
        for arm in ARMS:
            d[arm] = {k: mean([r["arms"][arm][k] for r in rs])
                      for k in ("top1", "top3", "top5", "rr", "dep_recall", "dep_precision",
                                "packed_tokens")}  # fmt: skip
        for base in ("G-distance", "BM25"):
            for k in ("top5", "rr"):
                diffs = [r["arms"]["RC-overlay"][k] - r["arms"][base][k] for r in rs]
                d[f"diff_{k}_RC_minus_{base}"] = {"mean": mean(diffs), "ci95": boot_ci(diffs)}
        agg["pools"][name] = d
    hs = [r for r in ok if r["family"] == "H"]
    non_h = [r for r in ok if r["family"] != "H"]
    agg["abstention"] = {
        "H_abstained": sum(r["abstain"] for r in hs),
        "H_n": len(hs),
        "false_abstain": sum(r["abstain"] for r in non_h),
        "non_H_n": len(non_h),
        "H_gold_top5": {arm: sum(r["arms"][arm]["top5"] for r in hs) for arm in ARMS},
    }
    agg["latency_ms"] = {
        "RC-overlay_median": statistics.median(r["ms"]["RC-overlay"] for r in ok) if ok else None,
        "RC-overlay_max": max((r["ms"]["RC-overlay"] for r in ok), default=None),
        "BM25_median": statistics.median(r["ms"]["BM25"] for r in ok) if ok else None,
        "G-distance_median": statistics.median(r["ms"]["G-distance"] for r in ok) if ok else None,
    }
    iok = [r for r in imp if not r.get("invalid")]
    ia: dict = {"n": len(iok), "prediction_matches": sum(r["prediction_matches"] for r in iok)}
    for arm in ("IMP-overlay", "IMP-graph", "BM25-select", "full-suite"):
        ia[arm] = {k: mean([r["arms"][arm].get(k) for r in iok])
                   for k in ("sel_recall", "frac_suite", "detected", "dep_recall", "direct_recall",
                             "dep_precision", "fp_flags", "flag_recall", "n_not_analysable",
                             "report_tokens", "ms", "hidden_leak")}  # fmt: skip
    agg["impact"] = ia
    return agg


def digest(obj) -> str:
    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items() if k not in ("ms", "tail")}
        if isinstance(o, list):
            return [clean(v) for v in o]
        if isinstance(o, float):
            return round(o, 9)
        return o

    return hashlib.sha256(json.dumps(clean(obj), sort_keys=True).encode()).hexdigest()


def evaluate(cases_dir: Path = CASES_DIR) -> tuple[list[dict], list[dict]]:
    rc, imp = [], []
    for c in load_cases(cases_dir):
        (imp if c["family"] == "F" else rc).append(
            run_impact_case(c) if c["family"] == "F" else run_rootcause_case(c)
        )
    return rc, imp


def validate(cases_dir: Path = CASES_DIR) -> list[str]:
    """Fixture validator: every hand-written ref resolves; the symptom test really fails (or, for
    F, base green and patched red). No scoring."""
    problems: list[str] = []
    for c in load_cases(cases_dir):
        tree = "base" if c["family"] == "F" else "repo"
        root = materialise(Path(c["_dir"]) / tree)
        try:
            g = build_graph(root, "v", cache_dir=None)
            og = build_overlay(g)
            refs = (c.get("chain", []) + c.get("gold", []) + c.get("extra_deps", [])
                    + c.get("decoys", []) + c.get("expected_dependants", []) + c.get("modified", []))  # fmt: skip
            for r in refs:
                if not node_of(og, r):
                    problems.append(f"{c['id']}: ref does not resolve in {tree}: {r}")
            for f in c.get("gold_files", []):
                if not (root / f).exists():
                    problems.append(f"{c['id']}: gold file missing {f}")
            if c["family"] != "F":
                parsed = parse_pytest(run_pytest(root, "--tb=short", "-rfE", "tests"))
                if c["primary_test"] not in parsed["failed"]:
                    problems.append(f"{c['id']}: primary test does not fail")
            else:
                if parse_pytest(run_pytest(root, "--tb=line", "-rfE", "tests"))["failed"]:
                    problems.append(f"{c['id']}: base suite is not green")
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)
    return problems


# ---- output --------------------------------------------------------------------------------
def write_outputs(out: Path, rc: list[dict], imp: list[dict], agg: dict, extra: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(
        json.dumps({**extra, **agg}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (out / "cases.json").write_text(
        json.dumps({"rootcause": rc, "impact": imp}, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with (out / "rootcause_metrics.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(
            [
                "case",
                "family",
                "arm",
                "rank",
                "top1",
                "top3",
                "top5",
                "rr",
                "file_rank",
                "dep_recall",
                "dep_precision",
                "packed_tokens",
                "decoys_in_top5",
                "abstain",
            ]
        )
        for r in rc:
            if r.get("invalid"):
                continue
            for arm in ARMS:
                a = r["arms"][arm]
                w.writerow(
                    [
                        r["id"],
                        r["family"],
                        arm,
                        a["rank"],
                        a["top1"],
                        a["top3"],
                        a["top5"],
                        f"{a['rr']:.4f}",
                        a["file_rank"],
                        f"{a['dep_recall']:.3f}",
                        f"{a['dep_precision']:.3f}",
                        a["packed_tokens"],
                        a["decoys_in_top5"],
                        int(r["abstain"]) if arm.startswith("RC") else "",
                    ]
                )
    with (out / "impact_metrics.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(
            [
                "case",
                "arm",
                "true_failing",
                "selected",
                "sel_recall",
                "frac_suite",
                "detected",
                "dep_recall",
                "direct_recall",
                "dep_precision",
                "fp_flags",
                "flag_recall",
            ]
        )
        for r in imp:
            if r.get("invalid"):
                continue
            for arm, a in r["arms"].items():
                w.writerow(
                    [
                        r["id"],
                        arm,
                        len(r["true_failing"]),
                        len(a["selected"]),
                        *(
                            ("" if a.get(k) is None else f"{a[k]:.3f}")
                            for k in (
                                "sel_recall",
                                "frac_suite",
                                "detected",
                                "dep_recall",
                                "direct_recall",
                                "dep_precision",
                                "fp_flags",
                                "flag_recall",
                            )
                        ),
                    ]
                )


def f3(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, default=CASES_DIR)
    ap.add_argument("--out", type=Path, default=REPO / "results" / "analysis" / "rootcause-eval")
    ap.add_argument("--validate-only", action="store_true")
    a = ap.parse_args(argv)
    if a.validate_only:
        probs = validate(a.cases)
        print("\n".join(probs) or "fixtures valid")
        return 1 if probs else 0
    rc1, imp1 = evaluate(a.cases)
    rc2, imp2 = evaluate(a.cases)
    deterministic = digest([rc1, imp1]) == digest([rc2, imp2])
    agg = aggregate(rc1, imp1)
    extra = {"deterministic_two_runs": deterministic, "token_cap": TOKEN_CAP, "top_k": TOP_K,
             "bootstrap": {"n": BOOT_N, "seed": BOOT_SEED},
             "priors_sha256": hashlib.sha256((Path(P.__file__)).read_bytes()).hexdigest(),
             "result_digest": digest([rc1, imp1])}  # fmt: skip
    write_outputs(a.out, rc1, imp1, agg, extra)
    print(json.dumps({"deterministic": deterministic, "invalid": agg["n_invalid"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
