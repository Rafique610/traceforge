"""P5-S04: build results/p5s04/table.csv (+ summary.json) from saved records. Stdlib only."""
import csv, json, statistics as st
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sel = json.loads((REPO / "results/final/selection-rc1.json").read_text("utf-8"))["selection"]
rows = []
for s in sel:
    c = s["case_id"]
    g = json.loads((REPO / f"results/final/final-axforge-G1/records/{c}.r0.json").read_text("utf-8"))
    rows.append(dict(model="glm-5.3-flash (RC1 recorded)", case=c, truth=s["cause_class"], rec=g, hw=None, status="ok"))
    hwp = REPO / f"results/p5s04/hw/{c}.json"
    hw = json.loads(hwp.read_text("utf-8")) if hwp.exists() else {"status": "missing"}
    rp = REPO / f"runs/p5s04/p5s04-{c}-G1-qwen35-4b-ctx12k-r0/records/{c}.r0.json"
    rec = json.loads(rp.read_text("utf-8")) if rp.exists() else None
    rows.append(dict(model="qwen3.5-4b-ctx12k (local)", case=c, truth=s["cause_class"], rec=rec, hw=hw, status=hw.get("status")))

def f(r):
    rec, hw = r["rec"], r["hw"]
    d = (rec or {}).get("diagnosis") or {}
    lat = rec["latency_ms"] if rec else None
    tout = rec["tokens_out"] if rec else None
    return {
        "model": r["model"], "case": r["case"], "truth_class": r["truth"], "run_status": r["status"],
        "outcome": rec["outcome"] if rec else "NO_RECORD", "verified": int(bool(rec and rec["outcome"] == "TEST_VERIFIED_IN_LAB" and rec.get("hidden_passed"))),
        "diag_class": d.get("cause_class"), "diag_correct": int(d.get("cause_class") == r["truth"]),
        "abstained": int(bool(d.get("abstained"))), "invalid_tool_calls": rec.get("invalid_tool_calls") if rec else None,
        "tool_calls": rec.get("tool_calls") if rec else None,
        "tokens_in": rec["tokens_in"] if rec else None, "tokens_out": tout, "latency_s": round(lat / 1000, 1) if lat else None,
        "tok_out_per_s_wall": round(tout / (lat / 1000), 2) if lat and tout else None,
        "wall_s": hw.get("wall_s") if hw else None,
        "gpu_mem_peak_mib": hw["hw"]["gpu_mem_peak_mib"] if hw and "hw" in hw else None,
        "ram_used_peak_mib": hw["hw"]["ram_used_peak_mib"] if hw and "hw" in hw else None,
        "failure_reason": (rec or {}).get("failure_reason"),
    }
out = [f(r) for r in rows]
with open(REPO / "results/p5s04/table.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)

def pct(v, p):
    v = sorted(v); k = (len(v) - 1) * p; lo = int(k); hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)
summ = {}
for m in dict.fromkeys(o["model"] for o in out):
    o = [x for x in out if x["model"] == m]
    lat = [x["latency_s"] for x in o if x["latency_s"]]
    gp = [x["gpu_mem_peak_mib"] for x in o if x["gpu_mem_peak_mib"]]
    rp = [x["ram_used_peak_mib"] for x in o if x["ram_used_peak_mib"]]
    ti = [x["tokens_in"] for x in o if x["tokens_in"] is not None]; to = [x["tokens_out"] for x in o if x["tokens_out"] is not None]
    summ[m] = {"n": len(o), "verified": sum(x["verified"] for x in o), "diag_correct": sum(x["diag_correct"] for x in o),
        "abstained": sum(x["abstained"] for x in o), "invalid_tool_calls": sum(x["invalid_tool_calls"] or 0 for x in o),
        "no_record_or_error": sum(1 for x in o if x["outcome"] in ("NO_RECORD",) or x["failure_reason"] and "provider" in str(x["failure_reason"])),
        "latency_median_s": round(st.median(lat), 1) if lat else None, "latency_p95_s": round(pct(lat, .95), 1) if lat else None,
        "tokens_in_total": sum(ti), "tokens_out_total": sum(to),
        "tok_out_per_s_median_wall": round(st.median([x["tok_out_per_s_wall"] for x in o if x["tok_out_per_s_wall"]]), 2) if any(x["tok_out_per_s_wall"] for x in o) else None,
        "gpu_mem_peak_mib_max": max(gp) if gp else None, "ram_used_peak_mib_max": max(rp) if rp else None,
        "outcomes": {k: sum(1 for x in o if x["outcome"] == k) for k in sorted({x["outcome"] for x in o})}}
(REPO / "results/p5s04/summary.json").write_text(json.dumps(summ, indent=1), "utf-8")
print(json.dumps(summ, indent=1))
