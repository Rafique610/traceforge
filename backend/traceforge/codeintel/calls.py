"""Static call resolution. Never guesses: dynamic calls that could hit in-repo code -> UNKNOWN."""

from .config import COMMON_METHODS
from .symbols import Symbols


def _candidate(attr: str | None, expr: str, repo_names: frozenset[str]) -> tuple[str, str] | None:
    """Attribute call on an untyped receiver: UNKNOWN only if an in-repo def has that name."""
    if attr and attr in repo_names and attr not in COMMON_METHODS and not attr.startswith("__"):
        return ("unknown", expr)
    return None


def resolve_call(
    sym: Symbols,
    rel: str,
    scope: dict,
    cls_id: str | None,
    qual: str | None,
    call: dict,
    repo_names: frozenset[str],
    is_module: bool,
) -> tuple[str, str, float] | None:
    """-> ("target", node id, confidence) | ("unknown", expr, 0) | None (external/builtin)."""
    form, chain = call["form"], call["chain"]
    locs = set(scope["locals"])
    if form in ("dyn", "dynattr"):
        r = (
            _candidate(call["attr"], call["expr"], repo_names)
            if form == "dynattr"
            else ("unknown", call["expr"])
        )
        return (*r, 0.0) if r else None
    expr = ".".join(chain)
    root = chain[0]
    if form == "name":
        nested = sym.func_in_scope(rel, qual, root)
        if nested:
            return ("target", nested, 1.0)
        ref = sym.lookup_def(rel, root)
        if root in locs and not (is_module and ref):
            return ("unknown", expr, 0.0)  # injected / local callable
        if ref and ref[0] in ("func", "class"):
            return ("target", sym.init_or_class(ref), 1.0)
        return None
    # attribute chain
    if root in ("self", "cls") and cls_id:
        m = sym.find_method(cls_id, chain[1]) if len(chain) == 2 else None
        if m:
            return ("target", m, 0.9)
        r = _candidate(chain[-1], expr, repo_names)
        return (*r, 0.0) if r else None
    if root in locs and not (is_module and sym.lookup_def(rel, root)):
        typ = scope["var_types"].get(root)
        ref = sym.resolve_chain(rel, typ) if typ else None
        if ref and ref[0] == "class" and len(chain) == 2:
            m = sym.find_method(ref[1], chain[1])
            if m:
                return ("target", m, 0.9)
        r = _candidate(chain[-1], expr, repo_names) if not (typ and ref is None) else None
        return (*r, 0.0) if r else None
    ref = sym.resolve_chain(rel, chain)
    if ref and ref[0] in ("func", "class"):
        return ("target", sym.init_or_class(ref), 1.0)
    return None
