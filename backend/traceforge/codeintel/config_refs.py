"""Config references found in Python source: env reads and Settings-field -> key bindings."""

import ast
import re

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ENV_METHODS = {"get", "pop", "setdefault"}


def chain(node: ast.AST) -> list[str] | None:
    """`a.b.c` -> ['a','b','c'] for Name/Attribute chains, else None."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return parts[::-1]
    return None


def env_key(node: ast.AST) -> str | None:
    """Key named by one env read: os.environ["K"], os.environ.get("K"), getenv("K"), env("K")."""
    if isinstance(node, ast.Subscript):
        c = chain(node.value)
        s = node.slice
        if c and c[-1] == "environ" and isinstance(s, ast.Constant) and isinstance(s.value, str):
            return s.value if KEY_RE.match(s.value) else None
        return None
    if isinstance(node, ast.Call) and node.args:
        a = node.args[0]
        if not (isinstance(a, ast.Constant) and isinstance(a.value, str) and KEY_RE.match(a.value)):
            return None
        c = chain(node.func)
        if not c:
            return None
        last = c[-1].lower()
        if last == "getenv" or "env" in last and last not in _ENV_METHODS:
            return a.value
        if last in _ENV_METHODS and "environ" in c[:-1]:
            return a.value
    return None


def env_key_in(expr: ast.AST | None) -> str | None:
    """First env key read anywhere inside an expression."""
    if expr is None:
        return None
    for n in ast.walk(expr):
        k = env_key(n)
        if k:
            return k
    return None


def field_alias(value: ast.AST | None) -> str | None:
    """Pydantic `Field(alias="X")` / `validation_alias="X"` -> X."""
    if isinstance(value, ast.Call):
        for kw in value.keywords:
            if (
                kw.arg in ("alias", "validation_alias")
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                return kw.value.value
    return None


def env_prefix(cls: ast.ClassDef) -> str | None:
    """`model_config = SettingsConfigDict(env_prefix="X_")` or inner `class Config`."""
    for st in cls.body:
        if isinstance(st, ast.Assign | ast.AnnAssign):
            tg = st.targets[0] if isinstance(st, ast.Assign) else st.target
            if isinstance(tg, ast.Name) and tg.id == "model_config" and st.value is not None:
                for n in ast.walk(st.value):
                    if (
                        isinstance(n, ast.keyword)
                        and n.arg == "env_prefix"
                        and isinstance(n.value, ast.Constant)
                    ):
                        return str(n.value.value)
        if isinstance(st, ast.ClassDef) and st.name == "Config":
            for sub in st.body:
                if (
                    isinstance(sub, ast.Assign)
                    and isinstance(sub.targets[0], ast.Name)
                    and sub.targets[0].id == "env_prefix"
                    and isinstance(sub.value, ast.Constant)
                ):
                    return str(sub.value.value)
    return None


def class_fields(cls: ast.ClassDef) -> list[dict]:
    """Annotated/assigned class-body names with an env key bound (explicit read or alias)."""
    out = []
    for st in cls.body:
        if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
            name, value = st.target.id, st.value
        elif isinstance(st, ast.Assign) and isinstance(st.targets[0], ast.Name):
            name, value = st.targets[0].id, st.value
        else:
            continue
        if name == "model_config" or name.startswith("_"):
            continue
        out.append(
            {
                "name": name,
                "line": st.lineno,
                "env_key": env_key_in(value),
                "alias": field_alias(value),
            }
        )
    return out
