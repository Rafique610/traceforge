"""P5-S11 preregistration validator: refuse to start a downstream run unless allowed.

Checks: ADR 0003 decision is `go`; an approved token budget is recorded; the arms are registered;
hypotheses, a recorded seeded case draw and replicates exist; the run directory is new and is not
under `results/final` (RC1 artifacts stay untouched). Zero provider calls; reads files only.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from traceforge.regression.retrieval_adapters import available_arms

ADR_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "adrs"
    / "0003-retrieval-architecture-decision.md"
)


class PreregistrationError(RuntimeError):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


class ExperimentSpec(BaseModel):
    name: str
    arms: list[str] = Field(min_length=1)
    hypotheses: list[str] = Field(default_factory=list)
    case_ids: list[str] = Field(default_factory=list)  # the seeded draw, recorded before any call
    seed: int | None = None
    replicates: int = 0
    token_ceiling: int = 0
    budget_approved_by: str = ""
    budget_approved_on: str = ""  # ISO date
    run_dir: str = ""
    excluded_case_ids: list[str] = Field(default_factory=list)  # the 35 analysed sites


def adr_decision(adr_path: Path = ADR_PATH) -> tuple[str, str]:
    """(decision, status): decision is 'go' | 'no-go' | 'none'; status is the ADR Status line."""
    text = adr_path.read_text("utf-8")
    m = re.search(r"^Status:\s*(.+)$", text, re.M)
    status = m.group(1).strip() if m else ""
    m = re.search(r"^## Decision\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    body = re.sub(r"[*_`]", "", m.group(1)).strip() if m else ""
    head = body.lower()[:60]
    if re.match(r"(decision:\s*)?no[- ]go\b", head):
        return "no-go", status
    if re.match(r"(decision:\s*)?go\b", head):
        return "go", status
    return "none", status


def validate_preregistration(
    spec: ExperimentSpec, adr_path: Path = ADR_PATH, arms_available: list[str] | None = None
) -> None:
    """Raise PreregistrationError (listing every reason) unless the run may start."""
    why: list[str] = []
    decision, status = adr_decision(adr_path)
    if decision != "go":
        why.append(
            f"ADR 0003 decision is {decision!r} (status: {status}); a downstream run needs 'go'"
        )
    if (
        spec.token_ceiling <= 0
        or not spec.budget_approved_by.strip()
        or not spec.budget_approved_on
    ):
        why.append("no approved token budget recorded (token_ceiling, budget_approved_by/on)")
    have = arms_available if arms_available is not None else available_arms()
    missing = [a for a in spec.arms if a not in have]
    if missing:
        why.append(f"arms not registered: {missing}")
    if not spec.hypotheses:
        why.append("no preregistered hypotheses")
    if not spec.case_ids or spec.seed is None:
        why.append("seeded case draw not recorded (case_ids and seed)")
    if spec.replicates < 1:
        why.append("replicates must be >= 1")
    if set(spec.case_ids) & set(spec.excluded_case_ids):
        why.append("case draw overlaps the analysed sites (never confirmation)")
    rd = spec.run_dir.replace("\\", "/")
    if not rd:
        why.append("run_dir missing")
    elif "results/final" in rd or Path(spec.run_dir).exists():
        why.append("run_dir must be new and outside results/final")
    if why:
        raise PreregistrationError(why)
