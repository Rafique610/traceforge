"""Diff/edit policy with explicit rejection reasons (path allowlist, no tests, D31 test_literal).

D31 `test_literal` rule (AST, defence in depth). A patch is rejected only when an ADDED literal
(present in the patched file but not in the old one) (a) also appears anywhere in the visible
test sources AND (b) sits in a special-casing position in the patched code:
  * a direct operand of ==, !=, in, not in;
  * the bare value of a `return` or an assignment right-hand side (also through a ternary
    branch or unary minus);
  * a direct element/key/value of a dict, list, set or tuple display (lookup tables), except in
    default parameter values;
  * a match-case value pattern.
Literals used arithmetically (BinOp operands, e.g. `price * pct / 100`), as call arguments or
keyword values (`f(x, 1000)`, `timeout=30`), as default parameters, in slices/subscripts, or in
ordering comparisons (<, >) are NOT flagged. 0, 1, -1, booleans, None, '' and single-character
strings are always exempt.
Limits: heuristic and bypassable (computed literals such as `100 + 100`, `int('42')`, names bound
elsewhere, string concatenation, non-literal tables). Hidden tests with different inputs are the
real guard; this only blocks the obvious copy-the-test-value patches.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import PurePosixPath

MAX_CHANGED_LINES = 60
MAX_FILES = 2
_TEST_NAME = re.compile(
    r"(^|/)(tests?|hidden_tests?)(/|$)|(^|/)(test_[^/]*|[^/]*_test\.py|conftest\.py)$"
)
_WIN_DRIVE = re.compile(r"^[A-Za-z]:")


@dataclass
class PolicyResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    changed_lines: int = 0
    signature_changed: bool = False


def check_paths(
    paths: Iterable[str], allowlist: Iterable[str], symlinks: Iterable[str] = ()
) -> list[str]:
    """Reasons to reject the paths alone (before any file is read)."""
    reasons: list[str] = []
    paths, allow, links = list(paths), set(allowlist), set(symlinks)
    if len(set(paths)) > MAX_FILES:
        reasons.append("too_many_files")
    for p in dict.fromkeys(paths):
        if p.startswith(("/", "\\")) or _WIN_DRIVE.match(p):
            reasons.append(f"absolute_path:{p}")
        elif "\\" in p or ".." in PurePosixPath(p).parts or p != str(PurePosixPath(p)):
            reasons.append(f"path_escape:{p}")
        elif _TEST_NAME.search(p):
            reasons.append(f"test_file:{p}")
        elif p not in allow:
            reasons.append(f"not_allowlisted:{p}")
        if p in links:
            reasons.append(f"symlink:{p}")
    return reasons


def _trivial(v: object) -> bool:
    return isinstance(v, bool) or v in (0, 1, -1, "") or (isinstance(v, str) and len(v) == 1)


def _literals(tree: ast.AST, special_only: bool = False) -> Counter:
    """Count non-trivial literals; with special_only, only those in special-casing positions."""
    parents: dict[ast.AST, ast.AST] = {}
    for n in ast.walk(tree):
        for ch in ast.iter_child_nodes(n):
            parents[ch] = n
    c: Counter = Counter()
    for n in ast.walk(tree):
        if not isinstance(n, ast.Constant) or not isinstance(n.value, (str, int, float)):
            continue
        v = n.value
        if _trivial(v) or (special_only and not _special(n, parents)):
            continue
        c[(type(v).__name__, v)] += 1
    return c


def _special(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    cur = node
    par = parents.get(cur)
    while isinstance(par, ast.UnaryOp) and isinstance(par.op, (ast.USub, ast.UAdd)):
        cur, par = par, parents.get(par)
    while isinstance(par, ast.IfExp) and cur is not par.test:
        cur, par = par, parents.get(par)
    if isinstance(par, ast.Compare):
        # left operand pairs with ops[0]; comparator i pairs with ops[i]
        ops = par.ops[:1] if cur is par.left else [par.ops[par.comparators.index(cur)]]
        return any(isinstance(o, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for o in ops)
    if isinstance(par, (ast.Return, ast.Assign, ast.AnnAssign, ast.NamedExpr)):
        return getattr(par, "value", None) is cur
    if isinstance(par, (ast.Dict, ast.List, ast.Set, ast.Tuple)):
        up = par
        while up is not None:
            if isinstance(up, ast.arguments):
                return False
            up = parents.get(up)
        return True
    return isinstance(par, ast.MatchValue)


def _sigs(tree: ast.AST) -> dict[str, str]:
    out: dict[str, str] = {}

    def walk(node: ast.AST, prefix: str) -> None:
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[prefix + ch.name] = ast.dump(ch.args)
                walk(ch, prefix + ch.name + ".")
            elif isinstance(ch, ast.ClassDef):
                walk(ch, prefix + ch.name + ".")

    walk(tree, "")
    return out


def check_patch(
    diff_text: str,
    old_files: dict[str, str],
    new_files: dict[str, str],
    visible_test_sources: Iterable[str] = (),
) -> PolicyResult:
    """Size, binary, syntax, signature and D31 `test_literal` checks on an applied edit."""
    res = PolicyResult(ok=True, changed_paths=sorted(new_files))
    res.changed_lines = sum(
        1 for ln in diff_text.splitlines() if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
    )
    if res.changed_lines > MAX_CHANGED_LINES:
        res.reasons.append("too_many_lines")
    test_lits: Counter = Counter()
    for src in visible_test_sources:
        try:
            test_lits += _literals(ast.parse(src))
        except SyntaxError:
            continue
    for path, text in new_files.items():
        if "\x00" in text:
            res.reasons.append(f"binary:{path}")
            continue
        if not path.endswith(".py"):
            continue
        try:
            new_tree = ast.parse(text)
        except SyntaxError:
            res.reasons.append(f"syntax_error:{path}")
            continue
        old_tree = ast.parse(old_files[path])
        added = _literals(new_tree, True) - _literals(old_tree, True)
        if set(added) & set(test_lits):
            res.reasons.append(f"test_literal:{path}")
        old_s, new_s = _sigs(old_tree), _sigs(new_tree)
        if any(k in new_s and old_s[k] != new_s[k] for k in old_s):
            res.signature_changed = True
    res.ok = not res.reasons
    return res
