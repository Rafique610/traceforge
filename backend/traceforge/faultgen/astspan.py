"""Gold line spans computed from the mutated source with `ast` (never typed by hand)."""

import ast


def _targets(node: ast.stmt) -> list[str]:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    if isinstance(node, ast.Assign):
        return [t.id for t in node.targets if isinstance(t, ast.Name)]
    return []


def find_node(source: str, qualname: str) -> ast.stmt:
    body: list[ast.stmt] = ast.parse(source).body
    parts = qualname.split(".")
    for depth, name in enumerate(parts):
        last = depth == len(parts) - 1
        match = None
        for node in body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if node.name == name:
                    match = node
            elif last and name in _targets(node):
                match = node
        if match is None:
            raise LookupError(f"{qualname!r} not found")
        if last:
            return match
        body = match.body  # type: ignore[union-attr]
    raise LookupError(qualname)


def find_span(source: str, qualname: str) -> tuple[int, int]:
    """(start_line, end_line), 1-based inclusive, of a def/class/assignment named by `qualname`."""
    node = find_node(source, qualname)
    return node.lineno, node.end_lineno or node.lineno


def is_def(source: str, qualname: str) -> bool:
    """True for a function/class (its bare name is a code symbol), False for a field/assignment."""
    return isinstance(
        find_node(source, qualname), ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    )


def test_ids(source: str, prefix: str) -> list[str]:
    """`<prefix>::<test_function>` for top-level test functions (visible/hidden id lists)."""
    return [
        f"{prefix}::{n.name}"
        for n in ast.parse(source).body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]
