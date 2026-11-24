"""Reporter-visible symptom text, derived deterministically from a case's committed data.

Sources: the visible reproducer (`datasets/reproducers/<id>/test_*.py`: its docstring and first
assertion) and the runtime metadata (`logs: suppressed`, live outage). Never the cause: the text is
scanned with the repo's leakage rules (gold terms, banned words) and the assertion detail is dropped
if it would trip them.
"""

import ast
import json
from pathlib import Path

from traceforge.contracts.case_manifest import CaseManifest
from traceforge.faultgen.leakage import gold_terms, scan_visible

MAX_DETAIL = 240


def _first_test(path: Path) -> tuple[str, str, str]:
    """(docstring, test name, first assert as source) of the first test function in the file."""
    tree = ast.parse(path.read_text("utf-8"))
    doc = (ast.get_docstring(tree) or "").removeprefix("Reproducer:").strip()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
            first = min(asserts, key=lambda n: n.lineno) if asserts else None
            return doc, node.name, ast.unparse(first.test) if first else ""
    return doc, "", ""


def _runtime(datasets: Path, case_id: str) -> dict:
    meta = datasets / "cases" / case_id / "meta.json"
    return json.loads(meta.read_text("utf-8")).get("runtime", {})


def _pristine_sources(case: CaseManifest, datasets: Path) -> dict[str, str]:
    out = {}
    for sym in case.gold_symbols:
        p = datasets.parent / sym.path
        if p.is_file():
            out[sym.path] = p.read_text("utf-8")
    return out


def symptom_for(case: CaseManifest, datasets: Path) -> str:
    runtime = _runtime(datasets, case.case_id)
    files = sorted((datasets / "reproducers" / case.case_id).glob("test_*.py"))
    doc, name, check = _first_test(files[0]) if files else ("", "", "")
    doc = doc[:1].upper() + doc[1:] if doc else f"Problem reported on {case.service}."
    parts = [doc]
    if runtime.get("symptom") == "intermittent":
        parts.append("The problem is intermittent.")
    if runtime.get("logs") == "suppressed":
        parts.append("Service logs are not available.")
    if runtime.get("stop"):
        parts.append("The service is degraded right now (live incident).")
    detail = ""
    if check:
        label = name.removeprefix("test_").replace("_", " ")
        detail = f"Reporter's check ({label}): expected `{check[:MAX_DETAIL]}` does not hold."
    terms = gold_terms(case, _pristine_sources(case, datasets), runtime)
    if detail and scan_visible({"symptom": " ".join([*parts, detail])}, terms):
        detail = ""  # never trade secrecy for detail
    return " ".join([*parts, *([detail] if detail else [])])
