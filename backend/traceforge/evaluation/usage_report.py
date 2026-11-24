"""Provider token ledgers, reported separately: `python -m traceforge.evaluation.usage_report`."""

import json
from pathlib import Path

from traceforge.agent import axforge, beatapi


def summarize(path: Path) -> dict:
    if not path.is_file():
        return {"requests": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    rows = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]
    live = [r for r in rows if r.get("type", "request") == "request"]
    i = sum(int(r.get("input_tokens") or 0) for r in live)
    o = sum(int(r.get("output_tokens") or 0) for r in live)
    return {
        "requests": len(live),
        "input_tokens": i,
        "output_tokens": o,
        "total_tokens": i + o,
        "unknown_usage_requests": sum(1 for r in live if r.get("usage_source") == "unknown"),
    }


def by_run(path: Path) -> dict:
    """AxForge tokens attributed to the run that was authorised when each row was written
    (reported + estimated for failed requests). `tier` follows the run id: `dev-*` runs are
    development spend even though they use the same AxForge allowance as official runs."""
    out: dict[str, dict] = {}
    if not path.is_file():
        return out
    run = "unattributed"
    for x in path.read_text("utf-8").splitlines():
        if not x.strip():
            continue
        r = json.loads(x)
        if r.get("type") == "authorization":
            run = r.get("run_id") or "unattributed"
            continue
        if r.get("type", "request") == "request":
            n = int(r.get("input_tokens") or 0) + int(r.get("output_tokens") or 0)
        else:
            n = int(r.get("estimated_tokens") or 0)
        d = out.setdefault(run, {"tokens": 0, "rows": 0})
        d["tokens"] += n
        d["rows"] += 1
    for k, d in out.items():
        d["tier"] = (
            "development"
            if k.startswith("dev-")
            else "final-rc1"
            if k.startswith("final-")
            else "official_or_unattributed"
        )
    return out


def slot_block(path: Path, ceiling: int) -> dict:
    """One key slot's totals: reported tokens, estimated failed-request tokens, room left."""
    b = summarize(path)
    est = axforge.totals(path)["estimated_tokens"] if path.is_file() else 0
    b["estimated_tokens_failed_requests"] = est
    b["committed_tokens"] = b["total_tokens"] + est
    b["ceiling"] = ceiling
    b["remaining_to_ceiling"] = ceiling - b["committed_tokens"]
    return b


def report(
    axforge_ledger: Path | None = None,
    beatapi_ledger: Path | None = None,
    axforge_ledger2: Path | None = None,
) -> dict:
    ax = summarize(axforge_ledger or axforge.LEDGER)
    path = axforge_ledger or axforge.LEDGER
    t = axforge.totals(path) if path.is_file() else {"estimated_tokens": 0, "committed_tokens": 0}
    ax["estimated_tokens_failed_requests"] = t["estimated_tokens"]
    committed = ax["total_tokens"] + t["estimated_tokens"]  # reported in+out, plus failed estimates
    ax["committed_tokens"] = committed
    ax["provider_free_allowance"] = axforge.ALLOWANCE
    ax["internal_ceiling"] = axforge.SAFETY_CEILING
    ax["safety_reserve"] = axforge.ALLOWANCE - axforge.SAFETY_CEILING
    ax["remaining_to_ceiling"] = axforge.SAFETY_CEILING - committed
    ax["high_water_mark"] = axforge._read_floor(path)
    ax["tier"] = "official"
    runs = by_run(path)
    ax["tokens_by_tier"] = {
        t: sum(d["tokens"] for d in runs.values() if d["tier"] == t)
        for t in ("development", "final-rc1", "official_or_unattributed")
    }
    ax["tokens_by_run"] = runs
    bt = summarize(beatapi_ledger or beatapi.LEDGER)
    bt["tier"] = "development"
    s1 = slot_block(path, axforge.SAFETY_CEILING)
    s2 = slot_block(axforge_ledger2 or axforge.LEDGER2, axforge.SAFETY_CEILING)
    committed2 = s1["committed_tokens"] + s2["committed_tokens"]
    combined = {
        "committed_tokens": committed2,
        "ceiling": axforge.COMBINED_CEILING,
        "remaining_to_ceiling": axforge.COMBINED_CEILING - committed2,
        "slot2_enabled": axforge.slot2_enabled(),
    }
    return {
        "axforge": ax,
        "beatapi": bt,
        "axforge_slots": {"1": s1, "2": s2},
        "axforge_combined": combined,
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
