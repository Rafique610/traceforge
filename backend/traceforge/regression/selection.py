"""Deterministic selection of VISIBLE tests from an ImpactReport."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from traceforge.regression.impact import ImpactReport


@dataclass(frozen=True)
class SelectedTest:
    test_id: str
    reason: str
    rank: int


@dataclass(frozen=True)
class Selection:
    tests: tuple[SelectedTest, ...] = ()
    fallback: str | None = None  # "full_suite" when nothing could be selected
    extra: dict = field(default_factory=dict)

    @property
    def ids(self) -> list[str]:
        return [t.test_id for t in self.tests]


def select_tests(
    report: ImpactReport, visible_tests: Sequence[str], limit: int | None = None
) -> Selection:
    """Ordered visible test ids: direct covering tests first, then transitive, ties by id.

    A report test is selectable if its id equals a visible id, or its file equals a file-level
    visible id (the id the runner reports is then the file). Nothing outside `visible_tests` is
    ever returned, whatever the report contains.
    """
    vis = list(dict.fromkeys(visible_tests))
    vis_set = set(vis)
    chosen: dict[str, SelectedTest] = {}
    for t in sorted(report.related_tests, key=lambda t: (t.depth, t.test_id)):
        vid = t.test_id if t.test_id in vis_set else (t.file if t.file in vis_set else None)
        if vid is None or vid in chosen:
            continue
        kind = "direct" if t.direct else f"transitive depth {t.depth}"
        reason = f"{kind} ({t.evidence_class}): " + " -> ".join(t.path)
        chosen[vid] = SelectedTest(vid, reason, len(chosen) + 1)
        if limit is not None and len(chosen) >= limit:
            break
    if not chosen:
        return Selection((), "full_suite")
    return Selection(tuple(chosen.values()))
