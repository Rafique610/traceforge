"""Diagnosis metrics over (record, manifest) pairs. Every metric carries num/den."""

from traceforge.evaluation.metrics.common import Pair, gold_targets, ratio


def _prf(pairs: list[Pair], cls: str) -> dict:
    """Precision/recall with `cls` as the positive class (predicted vs gold class)."""
    tp = sum(1 for r, m in pairs if r.diagnosis.cause_class == cls == m.cause_class)
    pred = sum(1 for r, _ in pairs if r.diagnosis.cause_class == cls)
    gold = sum(1 for _, m in pairs if m.cause_class == cls)
    return {"precision": ratio(tp, pred), "recall": ratio(tp, gold)}


def diagnosis_metrics(pairs: list[Pair]) -> dict:
    correct = sum(1 for r, m in pairs if r.diagnosis.cause_class == m.cause_class)
    with_target = [(r, m) for r, m in pairs if gold_targets(m)]
    top1 = sum(
        1
        for r, m in with_target
        if not r.diagnosis.abstained
        and r.diagnosis.target is not None
        and r.diagnosis.target in gold_targets(m)
    )
    confident = [(r, m) for r, m in pairs if not r.diagnosis.abstained]
    wrong = sum(1 for r, m in confident if r.diagnosis.cause_class != m.cause_class)
    return {
        "n": len(pairs),
        "cause_class_accuracy": ratio(correct, len(pairs)),
        # denominator: cases that have a gold key/symbol; an abstention or no target is a miss
        "exact_target_top1": ratio(top1, len(with_target)),
        # positive class = should abstain (gold insufficient_evidence)
        "abstention": _prf(pairs, "insufficient_evidence"),
        "runtime_dependency": _prf(pairs, "runtime_dependency"),
        # confident (non-abstaining) answers with the wrong class
        "misdiagnosis_rate": ratio(wrong, len(confident)),
        "abstained": ratio(sum(1 for r, _ in pairs if r.diagnosis.abstained), len(pairs)),
    }
