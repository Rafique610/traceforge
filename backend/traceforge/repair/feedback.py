"""Provenance-based feedback for the repair loop (condition F1).

A `FeedbackItem` can only be built from the result of a VISIBLE run: the visible reproducer or the
visible suite. `FeedbackItem.from_run("hidden", ...)` raises `FeedbackError`, and so does any
other suite name, so the hidden suite's output cannot be turned into feedback by construction.
Each item carries the suite, the failing test ids, the text and its sha256; the attempt record
stores the exact items delivered to the model.

`render_run` writes the text. A pytest log tail is mostly noise, so for every failing test it
keeps the assertion lines (`>` source line, `E` expected/actual messages) and falls back to the
raw tail only when no failure section can be parsed. Total length is capped (FEEDBACK_CAP).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from traceforge.contracts.test_run import TestRunResult

FEEDBACK_CAP = 2000
VISIBLE_SUITES = ("reproducer", "visible")
Source = Literal["visible_reproducer", "visible_suite"]
_SOURCE: dict[str, Source] = {"reproducer": "visible_reproducer", "visible": "visible_suite"}
_SECTION = re.compile(r"^_{3,} (.+?) _{3,}$", re.M)
_DETAIL = re.compile(r"^(?:>|E\s|[\w./\\-]+\.py:\d+:)")
_SHORT = re.compile(r"^(?:FAILED|ERROR) \S+", re.M)
MAX_DETAIL_LINES = 8
TRUNC = "\n[truncated]"


class FeedbackError(ValueError):
    """Feedback cannot be built from this source (anything that is not a visible run)."""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FeedbackItem:
    source: Source
    suite: Literal["reproducer", "visible"]
    test_ids: tuple[str, ...]
    text: str
    sha256: str

    def __post_init__(self) -> None:
        if self.suite not in VISIBLE_SUITES or _SOURCE.get(self.suite) != self.source:
            raise FeedbackError(f"feedback may only come from a visible run, not {self.suite!r}")
        if self.sha256 != sha256_text(self.text):
            raise FeedbackError("feedback sha256 does not match its text")

    @classmethod
    def from_run(cls, suite: str, result: TestRunResult, cap: int = FEEDBACK_CAP) -> FeedbackItem:
        if suite not in VISIBLE_SUITES:
            raise FeedbackError(f"feedback may only come from a visible run, not {suite!r}")
        ids = tuple(t.id for t in result.tests if t.outcome in ("failed", "error"))
        text = render_run(suite, result, ids, cap)
        return cls(_SOURCE[suite], suite, ids, text, sha256_text(text))  # type: ignore[arg-type]

    def provenance(self) -> dict:
        return {
            "source": self.source,
            "suite": self.suite,
            "test_ids": list(self.test_ids),
            "chars": len(self.text),
            "sha256": self.sha256,
        }


def _failure_details(tail: str) -> list[str]:
    """Per failing test: its name plus the assertion/expected-vs-actual lines."""
    marks = list(_SECTION.finditer(tail))
    out: list[str] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(tail)
        lines = [
            ln.rstrip()
            for ln in tail[m.end() : end].splitlines()
            if _DETAIL.match(ln) and not ln.startswith("=")
        ]
        out.append(f"{m.group(1)}:\n" + "\n".join(lines[:MAX_DETAIL_LINES]))
    return out


def render_run(suite: str, result: TestRunResult, ids: tuple[str, ...], cap: int) -> str:
    label = "reproducer" if suite == "reproducer" else "visible suite"
    head = f"{label}: {result.passed} passed, {result.failed} failed"
    if ids:
        head += "; failing: " + ", ".join(ids)
    tail = result.stdout_tail or ""
    body = "\n".join(_failure_details(tail))
    if not body:  # nothing parseable: the short-summary lines, else the raw tail
        short = [ln.strip() for ln in tail.splitlines() if _SHORT.match(ln)]
        body = "\n".join(short) or tail.strip()
    text = f"{head}\n{body}" if body else head
    if len(text) > cap:
        text = text[: max(cap - len(TRUNC), 0)] + TRUNC
    return text[:cap]


def build_feedback(
    repro: TestRunResult, visible: TestRunResult, cap: int = FEEDBACK_CAP
) -> tuple[FeedbackItem, ...]:
    """Items for one attempt: the reproducer and the visible suite, the cap split between them
    (a short one leaves its unused budget to the other)."""
    half = cap // 2
    a = FeedbackItem.from_run("reproducer", repro, half)
    b = FeedbackItem.from_run("visible", visible, cap - len(a.text) - 1)
    if len(a.text) >= half:  # reproducer was cut: it may use what the visible text left over
        a = FeedbackItem.from_run("reproducer", repro, cap - len(b.text) - 1)
    return (a, b)


def build_feedback_legacy(repro: TestRunResult, visible: TestRunResult) -> tuple[FeedbackItem, ...]:
    """The pipeline-v4 text, unchanged: raw log tails plus the failing ids (cap applied on
    delivery by `compose`). Kept so the formal v4 path behaves exactly as before."""
    bad = [t.id for t in visible.tests if t.outcome in ("failed", "error")]
    a = f"reproducer:\n{repro.stdout_tail}"
    b = f"visible suite:\n{visible.stdout_tail}\nfailing: {bad}"
    return (
        FeedbackItem("visible_reproducer", "reproducer", (), a, sha256_text(a)),
        FeedbackItem("visible_suite", "visible", tuple(bad), b, sha256_text(b)),
    )


def summarize_edit(diff: str, cap: int = 450) -> str:
    """Compact visible-side account of what the previous attempt changed (no hidden material)."""
    path, lines = "", []
    for ln in diff.splitlines():
        if ln.startswith("diff --git "):
            path = ln.rsplit(" b/", 1)[-1]
            lines.append(f"in {path}:")
        elif ln[:1] in "+-" and not ln.startswith(("+++", "---")):
            lines.append(ln)
    text = "\n".join(lines)
    return text if len(text) <= cap else text[: cap - len(TRUNC)] + TRUNC


def compose(
    items: tuple[FeedbackItem, ...], edit_summary: str | None, cap: int = FEEDBACK_CAP
) -> str:
    """The exact text delivered to the next attempt: your previous edit, then the test output.
    Never longer than `cap`; the edit summary is bounded, the test output gets the rest."""
    parts = [i.text for i in items]
    text = "\n".join(parts)
    if edit_summary:
        text = f"your previous edit:\n{edit_summary}\n{text}"
    return text[:cap]
