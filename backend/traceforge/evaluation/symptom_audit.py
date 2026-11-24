"""Evaluation-only audit: does a symptom contain gold terms (the fault's own identifiers)?

This reads gold symbols and the pristine source, so it must NEVER run inside the pipeline or feed
a prompt. It is run after a run, on the saved `symptom.json`/evidence, and reports findings.
"""

from pathlib import Path

from traceforge.agent.symptoms import _pristine_sources, _runtime
from traceforge.contracts.case_manifest import CaseManifest
from traceforge.faultgen.leakage import gold_terms, scan_visible


def audit(texts: list[str], case: CaseManifest, datasets: Path) -> list:
    """Leakage findings of the symptom texts against the case's gold terms (empty = clean)."""
    terms = gold_terms(case, _pristine_sources(case, datasets), _runtime(datasets, case.case_id))
    return list(scan_visible({"symptom": "\n".join(texts)}, terms))
