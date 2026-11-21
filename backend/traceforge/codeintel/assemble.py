"""Turn per-file facts + compose/.env facts into nodes and typed, provenance-carrying edges."""

import posixpath
import re
from pathlib import Path

from .builder import Builder, ModuleIndex
from .calls import resolve_call
from .compose_graph import add_compose, add_dotenv
from .config import UNKNOWN_PREFIX, GraphConfig
from .symbols import Symbols, cid, fid
from .tests_map import is_test_file, is_test_name

_CONF_ROOT = re.compile(r"setting|conf|cfg", re.I)


def _add_symbols(b: Builder, rel: str, f: dict, test_file: bool) -> None:
    file_id = f"file:{rel}"
    for c in f["classes"]:
        parent = c["qual"].rpartition(".")[0]
        owner = (
            cid(rel, parent)
            if parent and any(x["qual"] == parent for x in f["classes"])
            else file_id
        )
        b.node(
            cid(rel, c["qual"]),
            "class",
            path=rel,
            start=c["start"],
            end=c["end"],
            name=c["name"],
            qualname=c["qual"],
            signature=c["sig"],
            doc=c["doc"],
        )
        b.edge(cid(rel, c["qual"]), owner, "defined_in", "ast", f"{rel}:{c['start']}")
    quals = {fn["qual"] for fn in f["functions"]}
    for fn in f["functions"]:
        kind = "method" if fn["cls"] else "function"
        if test_file and is_test_name(fn["name"]):
            nid, kind = f"test:{rel}::{fn['qual']}", "test"
        else:
            nid = fid(rel, fn["qual"])
        parent = fn["qual"].rpartition(".")[0]
        if fn["cls"]:
            owner = cid(rel, fn["cls"])
        elif parent in quals:
            owner = fid(rel, parent)
        else:
            owner = file_id
        b.node(
            nid,
            kind,
            path=rel,
            start=fn["start"],
            end=fn["end"],
            name=fn["name"],
            qualname=fn["qual"],
            signature=fn["sig"],
            hash=fn["hash"],
            doc=fn["doc"],
        )
        b.edge(nid, owner, "defined_in", "ast", f"{rel}:{fn['start']}")


def _bind(
    b: Builder,
    sym: Symbols,
    by_name: dict,
    rel: str,
    cls_qual: str | None,
    name: str,
    key: str,
    line: int,
) -> None:
    owner = cid(rel, cls_qual) if cls_qual else f"file:{rel}"
    field_id = f"field:{rel}::{cls_qual + '.' if cls_qual else ''}{name}"
    prov = f"{rel}:{line}"
    b.node(field_id, "settings_field", path=rel, start=line, end=line, name=name)
    b.node(f"cfg:{key}", "config_key", path=rel, start=line, end=line, name=key)
    b.edge(field_id, f"cfg:{key}", "reads_config", "settings", prov)
    b.edge(field_id, owner, "defined_in", "ast", prov)
    if cls_qual:
        b.edge(owner, f"cfg:{key}", "declares_config", "settings", prov)
        by_name.setdefault(name, []).append((field_id, key, owner))
    else:
        sym.consts.setdefault(rel, {})[name] = field_id


def _bind_config(b: Builder, sym: Symbols, facts: dict[str, dict]) -> dict:
    by_name: dict[str, list] = {}
    for rel in sorted(facts):
        f = facts[rel]
        for c in f["consts"]:
            _bind(b, sym, by_name, rel, None, c["name"], c["key"], c["line"])
        for c in f["classes"]:
            for fld in c["fields"]:
                key = fld["env_key"] or fld["alias"]
                if not key and c["settings"]:
                    key = (c["prefix"] or "") + fld["name"]
                if key:
                    _bind(b, sym, by_name, rel, c["qual"], fld["name"], key.upper(), fld["line"])
        for kw in f["kw_bindings"]:
            ref = sym.resolve_chain(rel, kw["callee"])
            if ref and ref[0] == "class":
                crel, c = sym.class_info[ref[1]]
                _bind(b, sym, by_name, crel, c["qual"], kw["field"], kw["key"], kw["line"])
    return by_name


def _field_conf(scope: dict, a: dict, cls_id: str | None, owner: str) -> float | None:
    root = a["root"]
    if root in ("self", "cls"):
        return 0.9 if cls_id == owner else None
    if (root and _CONF_ROOT.search(root)) or (a["rootcall"] and _CONF_ROOT.search(a["rootcall"])):
        return 0.9
    typ = scope["var_types"].get(root or "")
    return 0.9 if typ and owner.endswith(f"::{typ[-1]}") else 0.5


def _scope_edges(b, sym, by_name, rel, scope, src, cls_id, qual, is_test, repo_names, is_module):
    covered = set()
    for call in scope["calls"]:
        r = resolve_call(sym, rel, scope, cls_id, qual, call, repo_names, is_module)
        if r is None:
            continue
        prov = f"{rel}:{call['line']}"
        if r[0] == "unknown":
            if not is_test:
                uid = b.node(f"{UNKNOWN_PREFIX}{r[1]}", "unknown", name=r[1])
                b.edge(src, uid, "calls", "ast", prov, b.unknown_conf, unknown=True)
        elif r[1] in b.nodes or r[1].startswith(("func:", "class:", "test:")):
            etype = "tests_covers" if is_test else "calls"
            covered.add(r[1])
            b.edge(src, r[1], etype, "ast", prov, r[2])
    for e in scope["env"]:
        kid = b.node(
            f"cfg:{e['key']}", "config_key", path=rel, start=e["line"], end=e["line"], name=e["key"]
        )
        b.edge(src, kid, "reads_config", "ast", f"{rel}:{e['line']}")
    for a in scope["attrs"]:
        ref = None
        if a["root"] and a["root"] not in ("self", "cls"):
            ref = sym.resolve_chain(rel, [a["root"], a["attr"]])
        if ref and ref[0] == "const":  # module.CONST bound to an env key
            _read_field(b, src, ref[1], rel, a["line"], 1.0)
            continue
        for field_id, key, owner in by_name.get(a["attr"], []):
            conf = _field_conf(scope, a, cls_id, owner)
            if conf:
                b.edge(
                    src,
                    f"cfg:{key}",
                    "reads_config",
                    "settings",
                    f"{rel}:{a['line']}",
                    conf,
                    via=field_id,
                )
    for name, line in scope["names"].items():
        ref = sym.lookup_def(rel, name)
        if not ref or (name in scope["locals"] and not is_module):
            continue
        if ref[0] == "const":
            _read_field(b, src, ref[1], rel, line, 1.0)
        elif is_test and ref[0] in ("func", "class") and ref[1] not in covered:
            b.edge(src, ref[1], "tests_covers", "ast", f"{rel}:{line}", 0.6)


def _read_field(b: Builder, src: str, field_id: str, rel: str, line: int, conf: float) -> None:
    key = next(d for (s, d, t, _p) in b.edges if s == field_id and t == "reads_config")
    b.edge(src, key, "reads_config", "settings", f"{rel}:{line}", conf, via=field_id)


def assemble(
    root: Path,
    facts: dict[str, dict],
    composes: dict[str, str],
    dotenvs: dict[str, list[dict]],
    cfg: GraphConfig,
) -> Builder:
    b = Builder(cfg.edge_weights)
    b.unknown_conf = cfg.unknown_confidence
    idx = ModuleIndex(sorted(facts), root.name if (root / "__init__.py").exists() else None)
    sym = Symbols(facts, idx)
    for rel in sorted(facts):
        err = facts[rel]["error"]
        b.node(
            f"file:{rel}",
            "file",
            path=rel,
            start=1,
            end=max(1, _n_lines(root, rel)),
            **({"error": err} if err else {}),
        )
    for rel in sorted([*composes, *dotenvs]):
        b.node(f"file:{rel}", "file", path=rel, start=1, end=1)
    add_compose(b, root, composes, dotenvs, idx)  # config files declare keys first
    add_dotenv(b, dotenvs)
    for rel in sorted(facts):
        _add_symbols(b, rel, facts[rel], is_test_file(rel))
    for src_rel, dst, line in sym.import_edges:
        b.edge(f"file:{src_rel}", f"file:{dst}", "imports", "ast", f"{src_rel}:{line}")
    by_name = _bind_config(b, sym, facts)
    repo_names = frozenset(fn["name"] for f in facts.values() for fn in f["functions"])
    for rel in sorted(facts):
        f = facts[rel]
        test_file = is_test_file(rel)
        if f["module"]:
            _scope_edges(
                b,
                sym,
                by_name,
                rel,
                f["module"],
                f"file:{rel}",
                None,
                None,
                False,
                repo_names,
                True,
            )
        for fn in f["functions"]:
            is_test = test_file and is_test_name(fn["name"])
            src = f"test:{rel}::{fn['qual']}" if is_test else fid(rel, fn["qual"])
            cls = cid(rel, fn["cls"]) if fn["cls"] else None
            _scope_edges(b, sym, by_name, rel, fn, src, cls, fn["qual"], is_test, repo_names, False)
    return b


def _n_lines(root: Path, rel: str) -> int:
    try:
        with open(root / posixpath.normpath(rel), "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 1
