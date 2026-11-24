"""Deterministic diagnostics: a small, general rule layer over the collected evidence.

Each rule reads evidence items (and the symptom items among them) and emits a `Finding`: one
sentence of a hint with the evidence ids it rests on and the id of the rule. Findings become
evidence items (kind `issue`, text starting with `FINDING`) appended after the evidence and the
symptom, so existing ids never change and retrieval and the diagnose prompt both see them.

A finding is a hint, never a verdict: it says what the evidence shows and where to look, not what
to change. Rules use no case names, gold labels, hidden tests or expected answers.
"""

from traceforge.diagnostics.rules import (
    FINDING_TAG,
    Finding,
    findings_as_items,
    is_finding,
    run_rules,
)

__all__ = ["FINDING_TAG", "Finding", "findings_as_items", "is_finding", "run_rules"]
