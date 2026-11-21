"""System metrics: latency, tokens, cost (actual + list price), tool-call hygiene."""

from traceforge.evaluation.metrics.common import Pair, median, percentile, ratio


def system_metrics(pairs: list[Pair]) -> dict:
    recs = [r for r, _ in pairs]
    n = len(recs)
    lat = [float(r.latency_ms) for r in recs]
    cost = sum(r.cost_usd for r in recs)
    listp = sum(r.list_price_usd for r in recs)
    tcalls = sum(r.tool_calls for r in recs)
    return {
        "n": n,
        "latency_ms": {"median": median(lat), "p95": percentile(lat, 0.95), "n": n},
        "tokens_in": {"total": sum(r.tokens_in for r in recs), "n": n},
        "tokens_out": {"total": sum(r.tokens_out for r in recs), "n": n},
        "cost_usd": {"total": cost, "per_run": (cost / n) if n else None, "n": n},
        "list_price_usd": {"total": listp, "per_run": (listp / n) if n else None, "n": n},
        "invalid_tool_call_rate": ratio(sum(r.invalid_tool_calls for r in recs), tcalls),
        # definition: cache hits / tool calls
        "cache_hit_rate": ratio(sum(r.cache_hits for r in recs), tcalls),
        "mean_attempts": {"value": (sum(r.attempts for r in recs) / n) if n else None, "n": n},
    }
