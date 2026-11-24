"""Patch scope (pipeline v5): an edit may touch only the diagnosed fault.

Confirmed finding (shop_api-013, patch_v4): the diagnosis named the redis port, and the patch fixed
the port and also rewrote the unrelated `redis_host` default, which failed the hidden suite. The
patch policy accepted it because only size, syntax, test literals and signatures were checked.

`make_scope_check(diag)` returns a function `(old_files, new_files) -> reasons` that rejects, with
the stable reason `edit_outside_diagnosed_target`:
  - configuration diagnosis (key K): any changed line (old or new) that does not mention K;
  - code diagnosis (path, qualname): a change in another file, or a changed line outside the
    diagnosed function/class/field's own line range in the base file.
It is general (derived from the diagnosis only, no case or key names) and never changes the edit;
a rejected attempt is recorded and the loop continues as for any other rejected edit.
"""

from __future__ import annotations

import ast
import difflib
from collections.abc import Callable, Iterator

REASON = "edit_outside_diagnosed_target"
ScopeCheck = Callable[[dict[str, str], dict[str, str]], list[str]]


def _hunks(old: str, new: str) -> Iterator[tuple[int, int, list[str], list[str]]]:
    a, b = old.splitlines(), new.splitlines()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != "equal":
            yield i1, i2, a[i1:i2], b[j1:j2]


def symbol_range(text: str, qualname: str) -> tuple[int, int] | None:
    """1-based (start, end) lines of a function, method, class or class field `qualname`."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    parts = qualname.split(".")

    def find(body: list[ast.stmt], rest: list[str]) -> tuple[int, int] | None:
        for n in body:
            name = getattr(n, "name", None)
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                name = n.target.id
            elif isinstance(n, ast.Assign) and len(n.targets) == 1:
                t = n.targets[0]
                name = t.id if isinstance(t, ast.Name) else name
            if name != rest[0]:
                continue
            if len(rest) == 1:
                return n.lineno, n.end_lineno or n.lineno
            if isinstance(n, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                return find(n.body, rest[1:])
        return None

    return find(tree.body, parts)


def _is_import_insertion(old: str, i1: int, olds: list[str], news: list[str]) -> bool:
    """A pure insertion of `import` / `from .. import ..` lines inside the module's leading
    import block (above the first non-import, non-docstring statement). Such a line cannot change
    behaviour by itself and is the usual companion of a fix that uses a new name."""
    if olds or not news:
        return False
    try:
        for ln in news:
            if ln.strip():
                body = ast.parse(ln.strip()).body
                if len(body) != 1 or not isinstance(body[0], ast.Import | ast.ImportFrom):
                    return False
        tree = ast.parse(old)
    except SyntaxError:
        return False
    for n in tree.body:
        is_doc = isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
        if not (isinstance(n, ast.Import | ast.ImportFrom) or is_doc):
            return i1 <= n.lineno - 1  # insertion at or above the first real statement
    return True


_TEXT = {
    REASON: "the edit changes code outside the diagnosed function or key; edit only that target",
    "malformed_edit": "the reply had no valid SEARCH/REPLACE block",
    "no_match": "SEARCH text was not found verbatim in the file; copy it from <source_file>",
    "ambiguous_match": "SEARCH text matches more than once; include more surrounding lines",
    "file_missing": "the file does not exist",
    "file_missing_or_binary": "the file does not exist or is not text",
    "too_many_files": "more than 2 files edited",
    "too_many_lines": "more than 60 changed lines",
    "test_literal": "a literal from the visible tests was hard-coded into the code",
    "syntax_error": "the edited file does not parse",
    "not_allowlisted": "the file may not be edited (only the service's own source and settings)",
    "test_file": "test files may not be edited",
    "patch_does_not_apply": "the patch does not apply to the base revision",
    "empty_diff": "the edit changes nothing",
}


def describe_reasons(reasons: list[str]) -> str:
    """Readable account of stable rejection codes (`code` or `code:path[:line]`)."""
    out = []
    for r in reasons:
        code, _, rest = r.partition(":")
        text = _TEXT.get(code) or _TEXT.get(r) or code
        out.append(f"{text} ({rest})" if rest else text)
    return "; ".join(out)


def make_scope_check(diag) -> ScopeCheck | None:  # noqa: ANN001 (SubmitDiagnosis)
    if diag is None:
        return None
    if diag.config_key:
        key = diag.config_key.rsplit(".", 1)[-1].lower()

        def check_config(old: dict[str, str], new: dict[str, str]) -> list[str]:
            reasons: list[str] = []
            for path in sorted(new):
                for i1, _i2, olds, news in _hunks(old[path], new[path]):
                    bad = [ln for ln in [*olds, *news] if ln.strip() and key not in ln.lower()]
                    if bad:
                        reasons.append(f"{REASON}:{path}:{i1 + 1}")
            return reasons

        return check_config
    if diag.path and diag.qualname:
        target, qual = diag.path, diag.qualname

        def check_code(old: dict[str, str], new: dict[str, str]) -> list[str]:
            reasons = [f"{REASON}:{p}" for p in sorted(new) if p != target]
            if target in new and (rng := symbol_range(old[target], qual)) is not None:
                start, end = rng
                for i1, i2, olds, news in _hunks(old[target], new[target]):
                    # 0-based [i1, i2) must lie within the symbol's lines (insertions at i1 == i2)
                    if (i1 < start - 1 or i2 > end) and not _is_import_insertion(
                        old[target], i1, olds, news
                    ):
                        reasons.append(f"{REASON}:{target}:{i1 + 1}")
            return reasons

        return check_code
    return None
