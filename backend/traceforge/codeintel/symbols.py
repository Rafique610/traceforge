"""Cross-file symbol tables: definitions, imports, name/attribute-chain resolution.

A resolved reference is a tuple (kind, value): ("func"|"class", node id), ("mod", rel path),
("const", field node id). `None` means external or not statically resolvable.
"""

from .builder import ModuleIndex

Ref = tuple[str, str]


def fid(rel: str, qual: str) -> str:
    return f"func:{rel}::{qual}"


def cid(rel: str, qual: str) -> str:
    return f"class:{rel}::{qual}"


class Symbols:
    def __init__(self, facts: dict[str, dict], idx: ModuleIndex):
        self.idx = idx
        self.top: dict[str, dict[str, Ref]] = {}
        self.funcs: dict[str, set[str]] = {}  # rel -> function quals (for nested lookup)
        self.methods: dict[str, dict[str, str]] = {}  # class id -> {method name: func id}
        self.class_info: dict[str, tuple[str, dict]] = {}  # class id -> (rel, class facts)
        self.mods: dict[str, dict[str, str]] = {}  # rel -> {alias (maybe dotted): module rel}
        self.syms: dict[str, dict[str, tuple[str, str]]] = {}  # rel -> {local: (rel, name)}
        self.ext: dict[str, set[str]] = {}  # rel -> locals bound to external imports
        self.consts: dict[str, dict[str, str]] = {}  # rel -> {NAME: field id}
        self.import_edges: list[tuple[str, str, int]] = []
        for rel in sorted(facts):
            f = facts[rel]
            top: dict[str, Ref] = {}
            self.funcs[rel] = {fn["qual"] for fn in f["functions"]}
            for c in f["classes"]:
                self.class_info[cid(rel, c["qual"])] = (rel, c)
                if "." not in c["qual"]:
                    top[c["name"]] = ("class", cid(rel, c["qual"]))
            for fn in f["functions"]:
                if fn["cls"]:
                    self.methods.setdefault(cid(rel, fn["cls"]), {})[fn["name"]] = fid(
                        rel, fn["qual"]
                    )
                elif "." not in fn["qual"]:
                    top[fn["name"]] = ("func", fid(rel, fn["qual"]))
            self.top[rel] = top
        for rel in sorted(facts):
            self._imports(rel, facts[rel]["imports"])

    def _imports(self, rel: str, imports: list[dict]) -> None:
        mods, syms, ext = {}, {}, set()
        for imp in imports:
            lvl, mod, line = imp["level"], imp["module"], imp["line"]
            if imp["names"] is None:  # import a.b.c [as x]
                tgt = self.idx.lookup(mod, rel)
                local = imp["as"] or mod.split(".")[0]
                key = imp["as"] or mod
                if tgt:
                    mods[key] = tgt
                    self.import_edges.append((rel, tgt, line))
                    if not imp["as"] and "." in mod:
                        mods[local] = self.idx.lookup(local, rel) or tgt
                else:
                    ext.add(local)
                continue
            base = self.idx.relative(rel, lvl, mod) if lvl else self.idx.lookup(mod, rel)
            if base:
                self.import_edges.append((rel, base, line))
            for name, asname in imp["names"]:
                local = asname or name
                sub = (
                    self.idx.relative(rel, lvl, f"{mod}.{name}" if mod else name)
                    if lvl
                    else self.idx.lookup(f"{mod}.{name}", rel)
                )
                if sub and (base is None or name not in self.top.get(base, {})):
                    mods[local] = sub
                    self.import_edges.append((rel, sub, line))
                elif base:
                    syms[local] = (base, name)
                else:
                    ext.add(local)
        self.mods[rel], self.syms[rel], self.ext[rel] = mods, syms, ext

    def lookup_def(self, rel: str, name: str, depth: int = 0) -> Ref | None:
        if name in self.top.get(rel, {}):
            return self.top[rel][name]
        if name in self.consts.get(rel, {}):
            return ("const", self.consts[rel][name])
        if depth < 4:
            if name in self.syms.get(rel, {}):
                t, n = self.syms[rel][name]
                return self.lookup_def(t, n, depth + 1)
            if name in self.mods.get(rel, {}):
                return ("mod", self.mods[rel][name])
        return None

    def find_method(self, class_id: str, name: str, seen: set[str] | None = None) -> str | None:
        seen = seen if seen is not None else set()
        if class_id in seen or class_id not in self.class_info:
            return None
        seen.add(class_id)
        if name in self.methods.get(class_id, {}):
            return self.methods[class_id][name]
        rel, c = self.class_info[class_id]
        for base in c["bases"]:
            ref = self.resolve_chain(rel, base.split("(")[0].split("."))
            if ref and ref[0] == "class":
                m = self.find_method(ref[1], name, seen)
                if m:
                    return m
        return None

    def resolve_chain(self, rel: str, chain: list[str]) -> Ref | None:
        """Resolve `a.b.c` as written in file `rel` to a definition, class or module."""
        mods = self.mods.get(rel, {})
        for k in range(len(chain), 0, -1):
            prefix = ".".join(chain[:k])
            if prefix in mods:
                return self._walk(("mod", mods[prefix]), chain[k:])
        ref = self.lookup_def(rel, chain[0])
        return self._walk(ref, chain[1:]) if ref else None

    def _walk(self, ref: Ref | None, rest: list[str]) -> Ref | None:
        for name in rest:
            if ref is None:
                return None
            if ref[0] == "mod":
                ref = self.lookup_def(ref[1], name)
            elif ref[0] == "class":
                m = self.find_method(ref[1], name)
                ref = ("func", m) if m else None
            else:
                return None
        return ref

    def func_in_scope(self, rel: str, qual: str | None, name: str) -> str | None:
        """Nested function `name` visible from function `qual` (enclosing functions only)."""
        parts = qual.split(".") if qual else []
        for i in range(len(parts), 0, -1):
            prefix = ".".join(parts[:i])
            if prefix in self.funcs[rel] and f"{prefix}.{name}" in self.funcs[rel]:
                return fid(rel, f"{prefix}.{name}")
        return None

    def init_or_class(self, ref: Ref) -> str:
        if ref[0] == "class":
            return self.find_method(ref[1], "__init__") or ref[1]
        return ref[1]
