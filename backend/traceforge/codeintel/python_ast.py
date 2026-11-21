"""One-pass AST extraction for a Python file into JSON-able 'facts' (cacheable per file hash).

Facts hold raw, unresolved references only; cross-file resolution happens in assemble.py.
Facts keys: error, imports, classes, functions, module, kw_bindings, consts. A scope
(function or module) holds: calls, env, attrs, names, locals, var_types.
"""

import ast
import hashlib

from .config_refs import chain, class_fields, env_key, env_key_in, env_prefix

_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)
_DEFS = (*_FUNCS, ast.ClassDef)


def walk_scope(stmts, *, classes: bool):
    """Nodes of one scope in deterministic order; nested defs are yielded but not entered.

    classes=True also enters class bodies (their statements belong to the enclosing scope).
    """
    stack = list(stmts)[::-1]
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, ast.ClassDef):
            if classes:
                stack.extend(reversed(n.body))
        elif not isinstance(n, _FUNCS):
            stack.extend(reversed(list(ast.iter_child_nodes(n))))


def _defs(stmts, prefix: str, cls: str | None):
    for n in walk_scope(stmts, classes=False):
        if isinstance(n, _DEFS):
            qual = f"{prefix}.{n.name}" if prefix else n.name
            yield n, qual, cls
            yield from _defs(n.body, qual, qual if isinstance(n, ast.ClassDef) else None)


def _root(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node


def _trim(s: str, n: int = 80) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


def _scan(stmts, params: list[str], ann: dict[str, list[str]]) -> dict:
    calls, env, attrs, names, locs = [], [], {}, {}, set(params)
    var_types = dict(ann)
    for n in walk_scope(stmts, classes=True):
        if isinstance(n, _DEFS):
            locs.add(n.name)  # nested def: name is local; resolved via its qualname later
        elif isinstance(n, ast.Call):
            c = chain(n.func)
            if isinstance(n.func, ast.Name):
                calls.append({"line": n.lineno, "form": "name", "chain": c})
            elif c:
                calls.append({"line": n.lineno, "form": "attr", "chain": c})
            else:
                is_attr = isinstance(n.func, ast.Attribute)
                calls.append(
                    {
                        "line": n.lineno,
                        "form": "dynattr" if is_attr else "dyn",
                        "chain": None,
                        "attr": n.func.attr if is_attr else None,
                        "expr": _trim(ast.unparse(n.func)),
                    }
                )
            k = env_key(n)
            if k:
                env.append({"line": n.lineno, "key": k})
        elif isinstance(n, ast.Subscript):
            k = env_key(n)
            if k:
                env.append({"line": n.lineno, "key": k})
        elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load):
            root = _root(n.value)
            rc = chain(root) if not isinstance(root, ast.Call) else None
            callee = chain(root.func) if isinstance(root, ast.Call) else None
            key = (n.attr, rc[0] if rc else None, callee[-1] if callee else None)
            attrs.setdefault(key, n.lineno)
        elif isinstance(n, ast.Name):
            if isinstance(n.ctx, ast.Load):
                names.setdefault(n.id, n.lineno)
            else:
                locs.add(n.id)
        elif isinstance(n, ast.arg):
            locs.add(n.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            locs.add(n.name)
        elif isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            if isinstance(n.value, ast.Call) and chain(n.value.func):
                var_types[n.targets[0].id] = chain(n.value.func)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            a = chain(n.annotation) if n.annotation is not None else None
            if a:
                var_types[n.target.id] = a
    return {
        "calls": calls,
        "env": env,
        "attrs": [
            {"line": ln, "attr": a, "root": r, "rootcall": rc} for (a, r, rc), ln in attrs.items()
        ],
        "names": names,
        "locals": sorted(locs),
        "var_types": var_types,
    }


def _signature(n) -> str:
    if isinstance(n, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in n.bases)
        return f"class {n.name}({bases})" if bases else f"class {n.name}"
    pre = "async def" if isinstance(n, ast.AsyncFunctionDef) else "def"
    ret = f" -> {ast.unparse(n.returns)}" if n.returns else ""
    return _trim(f"{pre} {n.name}({ast.unparse(n.args)}){ret}", 200)


def _doc(n) -> str:
    d = ast.get_docstring(n)
    return _trim(d.strip().splitlines()[0], 100) if d else ""


def _span(n) -> tuple[int, int]:
    start = min([n.lineno] + [d.lineno for d in n.decorator_list])
    return start, n.end_lineno or n.lineno


def _imports(tree) -> list[dict]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                out.append(
                    {"line": n.lineno, "level": 0, "module": a.name, "names": None, "as": a.asname}
                )
        elif isinstance(n, ast.ImportFrom):
            out.append(
                {
                    "line": n.lineno,
                    "level": n.level,
                    "module": n.module or "",
                    "names": [[a.name, a.asname] for a in n.names],
                    "as": None,
                }
            )
    return sorted(out, key=lambda i: (i["line"], i["module"]))


def _self_env_fields(fn, cls_fields: list[dict]) -> None:
    """`self.X = os.environ["K"]` inside a method binds field X of the class."""
    for st in walk_scope(fn.body, classes=False):
        if (
            isinstance(st, ast.Assign)
            and isinstance(st.targets[0], ast.Attribute)
            and isinstance(st.targets[0].value, ast.Name)
            and st.targets[0].value.id in ("self", "cls")
        ):
            k = env_key_in(st.value)
            if k:
                cls_fields.append(
                    {"name": st.targets[0].attr, "line": st.lineno, "env_key": k, "alias": None}
                )


def parse_python(src: str) -> dict:
    """Parse source into facts. A syntax error yields empty facts with `error` set."""
    facts: dict = {
        "error": None,
        "imports": [],
        "classes": [],
        "functions": [],
        "module": None,
        "kw_bindings": [],
        "consts": [],
    }
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError) as e:
        facts["error"] = (
            f"{type(e).__name__}: {getattr(e, 'msg', e)} (line {getattr(e, 'lineno', 0)})"
        )
        return facts
    lines = src.splitlines()
    facts["imports"] = _imports(tree)
    classes: dict[str, dict] = {}
    for node, qual, cls in _defs(tree.body, "", None):
        start, end = _span(node)
        if isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            classes[qual] = {
                "qual": qual,
                "name": node.name,
                "start": start,
                "end": end,
                "bases": bases,
                "settings": any(b.split(".")[-1] == "BaseSettings" for b in bases),
                "prefix": env_prefix(node),
                "fields": class_fields(node),
                "sig": _signature(node),
                "doc": _doc(node),
            }
            facts["classes"].append(classes[qual])
            continue
        a = node.args
        params = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg] if x]
        ann = {}
        for x in a.posonlyargs + a.args + a.kwonlyargs:
            t = chain(x.annotation) if x.annotation is not None else None
            if t:
                ann[x.arg] = t
        if cls in classes:
            _self_env_fields(node, classes[cls]["fields"])
        text = "\n".join(lines[start - 1 : end])
        facts["functions"].append(
            {
                "qual": qual,
                "name": node.name,
                "cls": cls,
                "start": start,
                "end": end,
                "sig": _signature(node),
                "hash": hashlib.sha1(text.encode()).hexdigest()[:12],
                "doc": _doc(node),
                **_scan(node.body, params, ann),
            }
        )
    facts["module"] = _scan(tree.body, [], {})
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            c = chain(n.func)
            for kw in n.keywords:
                k = env_key_in(kw.value)
                if kw.arg and k and c:
                    facts["kw_bindings"].append(
                        {"line": n.lineno, "callee": c, "field": kw.arg, "key": k}
                    )
    for st in tree.body:
        if isinstance(st, ast.Assign) and isinstance(st.targets[0], ast.Name):
            k = env_key_in(st.value)
            if k:
                facts["consts"].append({"name": st.targets[0].id, "line": st.lineno, "key": k})
    return facts
