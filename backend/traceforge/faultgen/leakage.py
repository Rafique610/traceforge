# ruff: noqa: E501
"""Leakage scan (model-visible files must not reveal the label) and visible/hidden input-overlap check (D31)."""

import ast
import re

from traceforge.contracts.case_manifest import CaseManifest
from traceforge.faultgen.astspan import is_def

BANNED_WORDS = re.compile(r"\b(bug|bugs|mutation|mutated)\b", re.IGNORECASE)
_IDENT = re.compile(
    r"^([a-z_][a-z0-9_]*|[A-Z][A-Z0-9_]*)$"
)  # field / env-var names are plumbing, not inputs
PLUMBING_STRS = {"127.0.0.1"}  # the stand-in broker address
PLUMBING_INTS = {6379}  # the stand-in broker's port


def gold_terms(m: CaseManifest, edited_sources: dict[str, str], runtime: dict) -> set[str]:
    """Strings that must not appear in any model-visible file of the case."""
    terms: set[str] = set(runtime.get("stop", []))
    for key in m.gold_config_keys:
        terms |= {key, key.split(".", 1)[-1]}
    for sym in m.gold_symbols:
        terms.add(sym.qualname)
        src = edited_sources.get(sym.path)
        # a bare function/class name is a code symbol; a bare field name (e.g. `quantity`) is public API
        if src is not None and is_def(src, sym.qualname):
            terms.add(sym.qualname.rsplit(".", 1)[-1])
    terms.add(m.fault_family)
    return {t for t in terms if t}


def scan_visible(files: dict[str, str], terms: set[str]) -> list[str]:
    problems = []
    for name, text in sorted(files.items()):
        for t in sorted(terms):
            if re.search(re.escape(t), text, re.IGNORECASE):
                problems.append(f"{name}: contains gold term {t!r}")
        if m := BANNED_WORDS.search(text):
            problems.append(f"{name}: contains the word {m.group(0)!r}")
    return problems


def input_literals(source: str) -> set[str]:
    """Constants used as inputs: skip `assert` statements, field-name-like strings, URL paths, tiny ints."""
    out: set[str] = set()

    def walk(node: ast.AST) -> None:
        if isinstance(node, ast.Assert):
            return
        if isinstance(node, ast.Constant) and not isinstance(node.value, bool):
            v = node.value
            if (
                isinstance(v, str)
                and len(v) >= 3
                and not _IDENT.match(v)
                and v not in PLUMBING_STRS
                and not v.startswith("/")
            ):
                out.add(v)
            elif isinstance(v, float) or (
                isinstance(v, int) and abs(v) >= 3 and v not in PLUMBING_INTS
            ):
                out.add(repr(v))
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(ast.parse(source))
    return out


def shared_inputs(visible: dict[str, str], hidden: dict[str, str]) -> list[str]:
    """Literals used as inputs by both a visible test and a hidden test (D31: must be empty)."""
    vis = set().union(
        *(input_literals(t) for n, t in visible.items() if n.startswith("test_")), set()
    )
    hid = set().union(
        *(input_literals(t) for n, t in hidden.items() if n.startswith("test_")), set()
    )
    return sorted(vis & hid)
