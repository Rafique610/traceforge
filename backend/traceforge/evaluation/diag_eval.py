# ruff: noqa: E501
"""Offline scoring of dev-d1 diagnosis runs (EVALUATION ONLY: reads gold labels and mutation patches).

Never imported by the pipeline and never feeds a prompt. For each saved case it reports the fixed
diagnosis metrics (class, file, function, evidence support, abstention, tool calls, tokens, latency,
retrieved-context relevance) and two validity indicators:
  - `identifier_exposed`: the gold function's name appears in the visible symptom (test ids, endpoint,
    assertion), i.e. the visible reproducer could localise it without reading source;
  - `source_reasoned`: the rationale quotes text of the faulty line itself, which the symptom does
    not contain (heuristic; the mutation patch is read here, offline, to know what that line is).
Usage: python -m traceforge.evaluation.diag_eval --manifest M --run L0=DIR --run G0=DIR [--out F]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def _read(p: Path):
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def _gold_targets(case: dict) -> set[str]:
    t = {f"{s['path']}::{s['qualname']}" for s in case["gold_symbols"]}
    t |= {f"{case['service']}.{k}" if "." not in k else k for k in case["gold_config_keys"]}
    return t


def _mutation_tokens(datasets: Path, case_id: str) -> set[str]:
    patch = datasets / "cases" / case_id / "mutation.patch"
    if not patch.exists():
        return set()
    toks: set[str] = set()
    for ln in patch.read_text("utf-8").splitlines():
        if ln[:1] in "+-" and not ln.startswith(("+++", "---")):
            toks |= {t for t in re.findall(r"[A-Za-z_]+\[[^\]]*\]|\w+\s*[-+*/=<>]+\s*\w+", ln)}
            toks |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*\[[^\]]+\]", ln))
    return {t.strip() for t in toks if len(t.strip()) >= 5}


def _gold_rank(rows: list[dict], gold_paths: set[str]) -> int | None:
    for i, r in enumerate(rows, 1):
        if f"{r['path']}::{r['id'].rsplit('::', 1)[-1]}" in gold_paths:
            return i
    return None


def score_case(run_dir: Path, case: dict, datasets: Path) -> dict | None:
    cid = case["case_id"]
    rec = _read(run_dir / "records" / f"{cid}.r0.json")
    d = run_dir / "cases" / f"{cid}.r0"
    if rec is None:
        return None
    meta, sub = _read(d / "run_meta.json"), _read(d / "diagnosis.json")
    trace = _read(d / "trace.json") or []
    sym, retr = _read(d / "symptom.json"), _read(d / "retrieval.json")
    sent, ev = _read(d / "context_sent.json"), _read(d / "evidence_v5.json")
    reqs = [json.loads(x) for x in (d / "requests.jsonl").read_text("utf-8").splitlines()]
    diag = rec["diagnosis"]
    gold = _gold_targets(case)
    gold_pq = {f"{s['path']}::{s['qualname']}" for s in case["gold_symbols"]}
    gold_files = {s["path"] for s in case["gold_symbols"]}
    target = diag.get("target")
    tpath = target.split("::")[0] if target and "::" in target else None
    ids = {i["id"] for i in (ev or {}).get("items", [])}
    cited = (sub or {}).get("supporting_evidence_ids", [])
    symptom_ids = {
        i["id"] for i in (ev or {}).get("items", []) if i["content"].startswith("SYMPTOM")
    }
    sent_ids = {f"{h['path']}::{h['id'].rsplit('::', 1)[-1]}" for h in (sent or {}).get("hits", [])}
    read_ok = sum(1 for t in trace if t["tool"] in ("read_symbol", "search_code") and t["ok"])
    text = "\n".join(json.dumps(i, default=str) for i in (sym or {}).get("items", [])).lower()
    leaf = [s["qualname"].rsplit(".", 1)[-1].lower() for s in case["gold_symbols"]]
    exposed = [q for q in leaf if q in text]
    rationale = (
        ((sub or {}).get("rationale") or "") + " " + ((sub or {}).get("observed_symptom") or "")
    )
    mut = _mutation_tokens(datasets, cid)
    quoted = sorted(t for t in mut if t in rationale)
    row = {
        "case": cid,
        "site": case["variant_group"],
        "arm": rec["condition"],
        "gold_class": case["cause_class"],
        "diag_class": diag["cause_class"],
        "target": target,
        "gold": sorted(gold),
        "correct_class": diag["cause_class"] == case["cause_class"],
        "correct_file": bool(tpath) and tpath in gold_files,
        "exact_function": bool(target) and target in gold,
        "abstained": diag["abstained"],
        "failure_reason": rec["failure_reason"],
        "cited": cited,
        "cited_all_exist": all(c in ids for c in cited),
        "cites_symptom": bool(set(cited) & symptom_ids),
        "target_in_context_sent": target in sent_ids if target else None,
        "source_reads_ok": read_ok,
        "unsupported_claims": [c for c in cited if c not in ids]
        + (
            ["target_never_seen"]
            if target and "::" in target and target not in sent_ids and read_ok == 0
            else []
        ),  # code targets only
        "tool_calls": rec["tool_calls"],
        "invalid_calls": rec["invalid_tool_calls"],
        "rejected_calls": (meta or {}).get("diagnosis_rejected_calls"),
        "tokens_in": rec["tokens_in"],
        "tokens_out": rec["tokens_out"],
        "model_s": ((meta or {}).get("timings") or {}).get("model_s"),
        "latency_ms": rec["latency_ms"],
        "requests": len(reqs),
        "request_errors": [r.get("error") for r in reqs if r.get("error")],
        "cache_hits": rec["cache_hits"],
        "tier": (meta or {}).get("tier"),
        "symptom_status": (meta or {}).get("symptom_status"),
        "symptom_has_raw_address": bool(re.search(r"0x[0-9a-fA-F]{6,}", text)),
        "code_fingerprint": ((meta or {}).get("code_fingerprint") or {}).get("sha256"),
        "identifier_exposed": exposed,
        "source_reasoned_quotes": quoted,
        "gold_in_context_sent": bool(gold_pq & sent_ids) if sent else None,
        "n_rendered": (sent or {}).get("n_rendered"),
        "n_retrieved": (sent or {}).get("n_retrieved"),
    }
    if retr:
        row["retrieval"] = {
            "gold_rank_L": _gold_rank(retr["L"], gold_pq), "gold_rank_G": _gold_rank(retr["G"], gold_pq),
            "n_L": len(retr["L"]), "n_G": len(retr["G"]), "overlap": retr["overlap"],
            "only_L": len(retr["only_L"]), "only_G": len(retr["only_G"]),
            "relevant_L": retr["relevant"]["L"], "relevant_G": retr["relevant"]["G"],
            "only_G_relevant": retr["only_G_relevant"], "only_L_relevant": retr["only_L_relevant"],
            "only_G_gold_file": [r["id"] for r in retr["G"] if r["id"] in retr["only_G"] and r["path"] in gold_files],
            "only_L_gold_file": [r["id"] for r in retr["L"] if r["id"] in retr["only_L"] and r["path"] in gold_files],
            "only_G_irrelevant": [r["id"] for r in retr["G"] if r["id"] in retr["only_G"] and not r["relevant_to_symptom"]],
            "only_L_irrelevant": [r["id"] for r in retr["L"] if r["id"] in retr["only_L"] and not r["relevant_to_symptom"]],
        }  # fmt: skip
    return row


def summarize(rows: list[dict]) -> dict:
    out: dict = {}
    for arm in sorted({r["arm"] for r in rows}):
        rs = [r for r in rows if r["arm"] == arm]
        by_site: dict = defaultdict(list)
        for r in rs:
            by_site[r["site"]].append(r)
        out[arm] = {
            "cases": len(rs),
            "correct_class": sum(r["correct_class"] for r in rs),
            "correct_file": sum(r["correct_file"] for r in rs),
            "exact_function": sum(r["exact_function"] for r in rs),
            "abstained": sum(r["abstained"] for r in rs),
            "unsupported_claims": sum(len(r["unsupported_claims"]) for r in rs),
            "tokens_in": sum(r["tokens_in"] for r in rs), "tokens_out": sum(r["tokens_out"] for r in rs),
            "tool_calls": sum(r["tool_calls"] for r in rs),
            "sites": {s: {"cases": len(v), "exact_function": sum(x["exact_function"] for x in v)}
                      for s, v in by_site.items()},
            "sites_with_at_least_one_exact": sum(any(x["exact_function"] for x in v) for v in by_site.values()),
        }  # fmt: skip
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--run", action="append", required=True, help="LABEL=run_dir (repeatable)")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    datasets = a.manifest.resolve().parents[1]
    cases = {c["case_id"]: c for c in json.loads(a.manifest.read_text("utf-8"))}
    rows = []
    for spec in a.run:
        label, _, path = spec.partition("=")
        for case in cases.values():
            r = score_case(Path(path), case, datasets)
            if r:
                r["run"] = label
                rows.append(r)
    doc = {"rows": rows, "summary": summarize(rows)}
    text = json.dumps(doc, indent=1)
    if a.out:
        a.out.write_text(text, "utf-8")
    print(json.dumps(doc["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
