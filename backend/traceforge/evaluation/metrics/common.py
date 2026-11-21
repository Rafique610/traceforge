"""Shared helpers: ratios with explicit numerator/denominator, percentiles, joins, grouping."""

import math
from collections import defaultdict
from collections.abc import Callable, Iterable

from traceforge.contracts.agent_run import AgentRunRecord
from traceforge.contracts.case_manifest import CaseManifest

Pair = tuple[AgentRunRecord, CaseManifest]


def ratio(num: int, den: int) -> dict:
    """Always report both counts; an empty denominator yields value None (never 0%)."""
    return {"num": num, "den": den, "value": (num / den) if den else None}


def mean_of(values: list[float]) -> dict:
    return {"value": (sum(values) / len(values)) if values else None, "n": len(values)}


def median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    mid = len(s) // 2
    return float(s[mid]) if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile: the ceil(q*n)-th smallest value (q in (0, 1])."""
    if not values:
        return None
    s = sorted(values)
    return float(s[max(math.ceil(q * len(s)), 1) - 1])


def join(records: Iterable[AgentRunRecord], manifests: Iterable[CaseManifest]) -> list[Pair]:
    """Pair each record with its manifest; unknown case ids and duplicate runs are errors."""
    by_id = {m.case_id: m for m in manifests}
    seen: set[tuple[str, str, int]] = set()
    out: list[Pair] = []
    for r in records:
        if r.case_id not in by_id:
            raise ValueError(f"record {r.run_id!r} references unknown case {r.case_id!r}")
        key = (r.case_id, r.condition, r.replicate)
        if key in seen:
            raise ValueError(f"duplicate record for case/condition/replicate {key}")
        seen.add(key)
        out.append((r, by_id[r.case_id]))
    return out


def group_by(items: Iterable, key: Callable) -> dict[str, list]:
    g: dict[str, list] = defaultdict(list)
    for it in items:
        g[str(key(it))].append(it)
    return dict(sorted(g.items()))


def distance_bucket(distance: int | None) -> str:
    if distance is None:
        return "none"
    return "2+" if distance >= 2 else str(distance)


def gold_targets(m: CaseManifest) -> set[str]:
    """Accepted exact targets: config keys and `path::qualname` symbols."""
    return set(m.gold_config_keys) | {f"{s.path}::{s.qualname}" for s in m.gold_symbols}


def gold_node_ids(m: CaseManifest) -> set[str]:
    """Retrieval relevance (binary): `cfg:<key>` and `sym:<path>::<qualname>` node ids."""
    return {f"cfg:{k}" for k in m.gold_config_keys} | {
        f"sym:{s.path}::{s.qualname}" for s in m.gold_symbols
    }
