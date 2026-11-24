"""Regression-evidence feedback: visible test id + visible assertion excerpt + impact path ONLY.

Hidden names, paths and content are refused (`LeakRefused`). The check is a marker check over the
final text (the guard's markers, the generic word markers of `agent.prompting.HIDDEN_MARKERS`
when importable, and an optional extra check such as `HiddenLeakGuard.check`).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence

from traceforge.contracts.test_run import TestRunResult
from traceforge.regression.impact import ImpactReport, is_hidden_path

try:  # reuse the e2e leak-guard vocabulary when available
    from traceforge.agent.prompting import HIDDEN_MARKERS as _WORD_MARKERS
except Exception:  # pragma: no cover
    _WORD_MARKERS = ("hidden",)

EXCERPT_LINES = 6
EXCERPT_CHARS = 600
_DETAIL = re.compile(r"^(?:>|E\s)")


class LeakRefused(ValueError):
    """The text would expose hidden-test material."""


class LeakGuard:
    def __init__(
        self,
        markers: Iterable[str] = (),
        hidden_paths: Iterable[str] = (),
        extra_check: Callable[[list[dict]], None] | None = None,
    ) -> None:
        self.markers = {m for m in markers if m}
        self.hidden_paths = list(hidden_paths)
        self.extra_check = extra_check

    def check(self, text: str) -> None:
        low = text.lower()
        for m in (*self.markers, *_WORD_MARKERS):
            if m.lower() in low:
                raise LeakRefused(f"hidden marker {m!r} in feedback")
        for pat in self.hidden_paths:
            if pat.strip("/") and pat.strip("/").lower() in low.replace("\\", "/"):
                raise LeakRefused(f"hidden path {pat!r} in feedback")
        if self.extra_check is not None:
            try:
                self.extra_check([{"role": "user", "content": text}])
            except AssertionError as e:
                raise LeakRefused(str(e)[:200]) from e


def _excerpt(stdout_tail: str, test_id: str) -> str:
    """Assertion lines of the failure section belonging to `test_id` (visible output only)."""
    name = test_id.split("::")[-1]
    sections = re.split(r"^_{3,} (.+?) _{3,}$", stdout_tail, flags=re.M)
    body = ""
    for i in range(1, len(sections) - 1, 2):
        if name in sections[i]:
            body = sections[i + 1]
            break
    lines = [ln.rstrip() for ln in (body or stdout_tail).splitlines() if _DETAIL.match(ln)]
    return "\n".join(lines[:EXCERPT_LINES])[:EXCERPT_CHARS]


def impact_path_for(report: ImpactReport, test_id: str) -> list[str]:
    for t in report.related_tests:
        if t.test_id == test_id or t.file == test_id:
            return t.path
    return []


def build_regression_feedback(
    result: TestRunResult,
    report: ImpactReport,
    visible_tests: Sequence[str],
    guard: LeakGuard,
    *,
    include_excerpt: bool = True,
    max_tests: int = 3,
) -> str:
    """Feedback for a visible dependant regression. Raises LeakRefused if anything is hidden."""
    vis = set(visible_tests)
    failing = [t.id for t in result.tests if t.outcome in ("failed", "error")]
    parts: list[str] = ["Your patch broke a visible dependant (regression evidence):"]
    for tid in failing[:max_tests]:
        if tid not in vis or is_hidden_path(tid.split("::")[0], guard.hidden_paths):
            raise LeakRefused(f"failing test {tid!r} is not a known visible test")
        parts.append(f"- visible test: {tid}")
        path = impact_path_for(report, tid)
        if path:
            parts.append("  impact path: " + " -> ".join(path))
        if include_excerpt:
            ex = _excerpt(result.stdout_tail, tid)
            if ex:
                parts.append("  assertion:\n" + "\n".join("    " + ln for ln in ex.splitlines()))
    if not failing:
        raise LeakRefused("no failing visible test to report")
    text = "\n".join(parts)
    guard.check(text)
    return text
