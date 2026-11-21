"""Repair metrics. Repairable = gold cause class in REPAIRABLE (never the predicted class)."""

from collections import Counter

from traceforge.contracts.case_manifest import REPAIRABLE
from traceforge.evaluation.metrics.common import Pair, ratio


def reason_codes(failure_reason: str | None) -> list[str]:
    """'a:path; b' -> ['a', 'b']: the stable code before any colon, per semicolon part."""
    if not failure_reason:
        return []
    return [p.split(":", 1)[0].strip() for p in failure_reason.split(";") if p.strip()]


def repair_metrics(pairs: list[Pair]) -> dict:
    rep = [(r, m) for r, m in pairs if m.cause_class in REPAIRABLE]
    n = len(rep)
    reasons = Counter(c for r, _ in pairs for c in set(reason_codes(r.failure_reason)))
    return {
        "n_repairable": n,
        "verified_repair_rate": ratio(sum(r.outcome == "TEST_VERIFIED_IN_LAB" for r, _ in rep), n),
        # patch_sha256 is only set once an edit parsed, applied and passed the policy, so this
        # is the apply rate (the record has no separate "applied" flag).
        "patch_apply_rate": ratio(sum(r.patch_sha256 is not None for r, _ in rep), n),
        "regressions": {
            "count": sum("visible_failed" in reason_codes(r.failure_reason) for r, _ in rep),
            "den": n,
        },
        "hidden_failed": {
            "count": sum("hidden_failed" in reason_codes(r.failure_reason) for r, _ in rep),
            "den": n,
        },
        "unverified": {"count": sum(r.outcome == "UNVERIFIED" for r, _ in rep), "den": n},
        "outcomes": dict(sorted(Counter(r.outcome for r, _ in rep).items())),
        # across ALL records of the group (a failure can occur on abstentions too)
        "failure_reasons": {
            "n_records": len(pairs),
            "counts": dict(sorted(reasons.items())),
        },
    }
