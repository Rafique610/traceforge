# ruff: noqa: E501
"""Change-impact report provider (P5-S15) on top of the P5-S12 overlay and traversal.

`make_provider()` is the factory `traceforge.regression.impact.get_impact_provider("s15")` loads.
The provider follows the `ImpactProvider` protocol: deterministic, offline, zero tokens, visible
tests only, hidden paths dropped from the graph before anything is computed, no secret values.
Static analysis only: dependants it does not see are listed under `not_analysable`, never denied.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from pathlib import Path

import yaml

from traceforge.analysis import priors as P
from traceforge.analysis.overlay import OverlayGraph, build_overlay
from traceforge.analysis.traversal import (
    IMPACT_CONFIG,
    Reached,
    traverse,
    unknown_sites,
)
from traceforge.codeintel import build_graph
from traceforge.codeintel.config import SKIP_DIRS
from traceforge.codeintel.config_refs import env_key
from traceforge.codeintel.queries import changed_symbols, signature_changes
from traceforge.regression.impact import (
    ChangedSymbol,
    ConfigConsumer,
    Dependant,
    ImpactReport,
    NotAnalysable,
    RelatedTest,
    RiskFlag,
    is_hidden_path,
)

IMPACT_TYPES = (*P.REVERSE_TYPES, *P.TEST_TYPES)
SECRET = re.compile(r"SECRET|PASSW|TOKEN|API_?KEY|PRIVATE|CREDENTIAL|DSN|AUTH", re.I)
_EV_ORDER = {"observed": 0, "static": 0, "inferred": 1, "unknown": 2}


def _strip(nid: str) -> str:
    return nid[5:] if nid.startswith("test:") else nid


def _redact(key: str, value: str | None) -> str:
    if value is None:
        return "(none)"
    return (
        "[redacted]" if SECRET.search(key) else (value if len(value) <= 40 else value[:37] + "...")
    )


# ---- config default / compose value diff ---------------------------------------------------
def config_values(root: str | Path) -> dict[tuple[str, str], str]:
    """(file, KEY) -> literal default text. Python `getenv("K", default)` and compose env values.

    `.env` files are NOT read (names or values). Secret-named values are redacted on output."""
    root = Path(root)
    out: dict[tuple[str, str], str] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        rel = p.relative_to(root).as_posix()
        try:
            if p.suffix == ".py":
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
                for n in ast.walk(tree):
                    k = env_key(n) if isinstance(n, ast.Call) else None
                    if k and len(n.args) > 1:  # type: ignore[union-attr]
                        out[(rel, k)] = ast.unparse(n.args[1])  # type: ignore[union-attr]
                    elif k and isinstance(n, ast.Call):
                        out.setdefault((rel, k), "(no default)")
            elif re.match(r"^(docker-)?compose([.-].+)?\.ya?ml$", p.name):
                doc = yaml.safe_load(p.read_text(encoding="utf-8", errors="replace")) or {}
                for sname, svc in sorted((doc.get("services") or {}).items()):
                    env = (svc or {}).get("environment") or {}
                    items = (
                        list(env.items()) if isinstance(env, dict)
                        else [((str(e).split("=", 1) + [""])[:2]) for e in env]
                    )  # fmt: skip
                    for k, v in items:
                        out[(f"{rel}#{sname}", str(k))] = str(v)
        except (SyntaxError, ValueError, yaml.YAMLError, OSError, AttributeError):
            continue
    return out


def config_changes(base: str | Path, patched: str | Path) -> list[tuple[str, str, str, str]]:
    """(key, file, kind, detail) for added / removed / changed defaults or compose values."""
    a, b = config_values(base), config_values(patched)
    out = []
    for fk in sorted(set(a) | set(b)):
        f, key = fk
        if a.get(fk) == b.get(fk):
            continue
        kind = "added" if fk not in a else "removed" if fk not in b else "changed"
        out.append((key, f, kind, f"{_redact(key, a.get(fk))} -> {_redact(key, b.get(fk))}"))
    return out


def _imports_name(path: Path, name: str) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return False
    return any(
        isinstance(n, ast.ImportFrom) and any(a.name == name for a in n.names)
        for n in ast.walk(tree)
    )


def stale_import_breaks(og: OverlayGraph, root: Path, removed: Sequence[str]):
    """Files that `from X import <removed name>` and the files importing those (<= 3 hops).

    Such files raise ImportError at load time, so every test inside them fails even when the test
    never calls the removed symbol. -> list of (removed symbol, file, hops)."""
    out: list[tuple[str, str, int]] = []
    for sym in removed:
        d = og.node(sym)
        if d["kind"] not in ("function", "class") or "." in d.get("qualname", ""):
            continue
        seen: dict[str, int] = {}
        queue: list[str] = []
        for e in og.edges_from(f"file:{d['path']}", ("imported_by",)):
            p = e.dst[5:]
            if _imports_name(root / p, d["name"]):
                seen[p] = 1
                queue.append(p)
        while queue:
            p = queue.pop(0)
            if seen[p] >= P.IMPACT_DEPTH:
                continue
            for e in og.edges_from(f"file:{p}", ("imported_by",)):
                q = e.dst[5:]
                if q not in seen:
                    seen[q] = seen[p] + 1
                    queue.append(q)
        out += [(sym, p, h) for p, h in sorted(seen.items())]
    return out


class OverlayImpactProvider:
    name = "s15"

    def __init__(self, max_depth: int = P.IMPACT_DEPTH) -> None:
        self.max_depth = max_depth

    # -- helpers --------------------------------------------------------------------------
    def _traverse(self, og: OverlayGraph, roots: Sequence[str]) -> list[Reached]:
        cfg = IMPACT_CONFIG.with_depth(reverse=self.max_depth)
        merged: dict[str, Reached] = {}
        for root in sorted(roots):
            for r in traverse(og, [root], "reverse", cfg, types=(*IMPACT_TYPES, "overrides")):
                cur = merged.get(r.node)
                if cur is None or (r.depth, r.node) < (cur.depth, cur.node):
                    merged[r.node] = r
        return sorted(merged.values(), key=lambda r: (r.depth, r.node))

    def analyse(
        self,
        base_root: str | Path,
        patched_root: str | Path,
        *,
        visible_tests: Sequence[str],
        hidden_paths: Sequence[str] = (),
        seeds: Sequence[str] = (),
    ) -> ImpactReport:
        hid, vis = list(hidden_paths), set(visible_tests)
        old = build_graph(base_root, "base", cache_dir=None)
        new = build_graph(patched_root, "patched", cache_dir=None)
        og_new = build_overlay(new, hidden_paths=hid)
        og_old = build_overlay(old, hidden_paths=hid)
        sigs = signature_changes(old, new)

        def path_of(nid: str) -> str | None:
            for g in (og_new, og_old):
                if nid in g:
                    return g.path_of(nid)
            return None

        def visible_id(nid: str, g: OverlayGraph) -> str | None:
            p = g.path_of(nid)
            if is_hidden_path(p, hid):
                return None
            raw = _strip(nid)
            file, _, qual = raw.partition("::")
            for cand in (raw, f"{file}::{qual.replace('.', '::')}" if qual else raw):
                if cand in vis:
                    return cand
            return p if p in vis else None

        changed = [c for c in changed_symbols(old, new) if not is_hidden_path(path_of(c), hid)]
        prod_changed = [c for c in changed if not c.startswith("test:")]
        cfg_ch = config_changes(base_root, patched_root)
        cfg_keys = sorted({f"cfg:{k}" for k, *_ in cfg_ch})
        seed_ids = sorted(
            set(prod_changed) | set(cfg_keys) | {s for s in seeds if s in og_new or s in og_old}
        )
        sig_set = {c for c in seed_ids if c in sigs}
        removed = [c for c in prod_changed if c not in new and c in old]
        live = [s for s in seed_ids if s in og_new]

        modified: list[ChangedSymbol] = []
        for c in seed_ids:
            if c.startswith("cfg:") and c in cfg_keys:
                where = next(f for k, f, *_ in cfg_ch if f"cfg:{k}" == c)
                modified.append(ChangedSymbol(id=c, change="body", path=where.split("#")[0]))
                continue
            a = old.node(c).get("signature") if c in old else None
            b = new.node(c).get("signature") if c in new else None
            if c not in changed:
                kind = "seed"
            elif c not in old:
                kind = "added"
            elif c not in new:
                kind = "removed"
            else:
                kind = "signature" if a != b else "body"
            modified.append(
                ChangedSymbol(id=c, change=kind, path=path_of(c), old_signature=a, new_signature=b)
            )
        files = sorted({m.path for m in modified if m.path})

        reached = self._traverse(og_new, live)
        old_reached = [
            r for r in (self._traverse(og_old, removed) if removed else [])
            if r.node not in changed  # a dependant edited by the patch may have been updated
        ]  # fmt: skip
        by_id: dict[str, tuple[Reached, OverlayGraph]] = {}
        for rs, og in ((reached, og_new), (old_reached, og_old)):
            for r in rs:
                if r.node not in by_id or r.depth < by_id[r.node][0].depth:
                    by_id[r.node] = (r, og)

        deps: list[Dependant] = []
        tests: list[RelatedTest] = []
        cfgs: list[ConfigConsumer] = []
        for nid in sorted(by_id, key=lambda n: (by_id[n][0].depth, n)):
            r, og = by_id[nid]
            chain = [r.steps[0].src, *[s.dst for s in r.steps]]
            kind = og.kind(nid)
            p = og.path_of(nid)
            if is_hidden_path(p, hid) or any(is_hidden_path(og.path_of(c), hid) for c in chain):
                continue
            if kind == "test":
                vid = visible_id(nid, og)
                if vid is not None:
                    tests.append(RelatedTest(
                        test_id=vid, file=p, depth=r.depth, direct=r.depth == 1,
                        path=[_strip(c) for c in chain], evidence_class=r.evidence, rank=0,
                    ))  # fmt: skip
                continue
            if kind in ("file", "settings_field", "service", "unknown") or r.depth > self.max_depth:
                continue
            brk = r.depth == 1 and r.steps[0].type == "called_by" and chain[0] in sig_set
            deps.append(Dependant(
                id=nid, depth=r.depth, path=chain, via=r.steps[-1].type,
                evidence_class=r.evidence, breaking=brk, file=p,
            ))  # fmt: skip
            if chain[0].startswith("cfg:") and r.steps[-1].type == "read_by":
                cfgs.append(ConfigConsumer(config_key=chain[0], consumer=nid, depth=r.depth,
                                           evidence_class=r.evidence))  # fmt: skip
        # removed/renamed symbol: importers fail at load time (every test in those files)
        breaks = stale_import_breaks(og_old, Path(base_root), [r for r in removed if r in og_old])
        tests_by_file: dict[str, list[str]] = {}
        for tn, td in og_old.nx.nodes(data=True):
            if td["kind"] == "test":
                tests_by_file.setdefault(td["path"], []).append(tn)
        for sym, f, h in breaks:
            for tn in sorted(tests_by_file.get(f, [])):
                vid = visible_id(tn, og_old)
                if vid is not None:
                    tests.append(RelatedTest(
                        test_id=vid, file=f, depth=h, direct=h == 1,
                        path=[sym, f"file:{f}", _strip(tn)], evidence_class="static", rank=0,
                    ))  # fmt: skip
        deps.sort(key=lambda d: (d.depth, d.id))
        direct = [d for d in deps if d.depth == 1]
        trans = [d for d in deps if d.depth > 1]
        seen_t: dict[str, RelatedTest] = {}
        for t in sorted(tests, key=lambda t: (t.depth, _EV_ORDER[t.evidence_class], t.test_id)):
            seen_t.setdefault(t.test_id, t)
        tests = [t.model_copy(update={"rank": i + 1}) for i, t in enumerate(seen_t.values())]
        cfgs.sort(key=lambda c: (c.config_key, c.depth, c.consumer))

        flags: list[RiskFlag] = []
        notan: dict[tuple[str, str], NotAnalysable] = {}

        def na(subject: str, reason: str) -> None:
            notan[(subject, reason)] = NotAnalysable(subject=subject, reason=reason)

        seed_set = set(seed_ids)
        stale = {d.id for d in deps if d.id in {r.node for r in old_reached}}
        for m in modified:
            outside = [
                d for d in direct
                if d.path[0] == m.id and d.id not in seed_set and d.via == "called_by"
            ]  # fmt: skip
            if m.change == "signature" and outside:
                flags.append(RiskFlag(
                    code="signature_change_external_callers", subject=m.id,
                    detail=f"{len(outside)} caller(s) outside the patch: "
                    + ", ".join(f"{d.id} [{d.evidence_class}]" for d in outside[:5]),
                ))  # fmt: skip
            overriders = [d for d in deps if d.path[0] == m.id and d.via == "overridden_by"]
            if m.change == "signature" and overriders:
                flags.append(RiskFlag(
                    code="signature_change_overriders", subject=m.id,
                    detail="overridden in: " + ", ".join(d.id for d in overriders[:5]),
                ))  # fmt: skip
            if m.change == "removed":
                refs = [d for d in direct if d.path[0] == m.id and d.id in stale]
                if refs:
                    renamed = [
                        n for n in new.nx.nodes
                        if n not in old and old.node(m.id).get("hash")
                        and new.node(n).get("hash") == old.node(m.id).get("hash")
                    ]  # fmt: skip
                    hint = f"; same body now at {renamed[0]} (rename)" if renamed else ""
                    flags.append(RiskFlag(
                        code="removed_symbol_still_referenced", subject=m.id,
                        detail=", ".join(d.id for d in refs[:5]) + hint,
                    ))  # fmt: skip
            if m.change in ("body", "signature", "added") and not m.id.startswith("cfg:"):
                na(m.id, "contract changes the graph cannot see "
                         "(return type, raised exception, side effect)")  # fmt: skip
            g = og_new if m.id in og_new else og_old
            for site in unknown_sites(g, m.id):
                resolved = [
                    1 for _u, _v, e in g.nx.out_edges(m.id, data=True) if e.get("name_resolved")
                ]  # fmt: skip
                tail = (
                    f"name-resolved to {len(resolved)} inferred candidate(s)"
                    if resolved
                    else "no in-repo candidate"
                )
                na(
                    f"{m.id} -> {site.split(' @ ')[0]}",
                    f"unknown call site / dynamic dispatch; {tail}",
                )
        for sym in sorted({b[0] for b in breaks}):
            fl = [
                f"{f} (hop {h})" for s_, f, h in breaks if s_ == sym and not is_hidden_path(f, hid)
            ]
            flags.append(RiskFlag(code="import_time_break", subject=sym,
                                  detail="importers fail at load: " + ", ".join(fl[:8])))  # fmt: skip
        for key, f, kind, detail in cfg_ch:
            n = sum(1 for c in cfgs if c.config_key == f"cfg:{key}")
            flags.append(RiskFlag(code="config_default_changed", subject=f"cfg:{key}",
                                  detail=f"{kind} in {f}: {detail}; {n} consumer(s) found"))  # fmt: skip
        for s in seeds:
            if s.startswith("cfg:") and s not in cfg_keys:
                n = sum(1 for c in cfgs if c.config_key == s)
                if n:
                    flags.append(RiskFlag(code="config_key_read_elsewhere", subject=s,
                                          detail=f"{n} consumer(s)"))  # fmt: skip
        blind = "no test coverage: this check is blind here"
        for m in modified:
            if m.change != "seed" and not any(m.id in t.path for t in tests):
                na(m.id, blind)
        for d in direct:
            if not any(d.id in t.path for t in tests):
                na(d.id, blind)
        flags.sort(key=lambda f: (f.code, f.subject))
        return ImpactReport(
            provider=self.name, modified_files=files, modified_symbols=modified,
            direct_dependants=direct, transitive_dependants=trans, config_consumers=cfgs,
            related_tests=tests, risk_flags=flags,
            not_analysable=[notan[k] for k in sorted(notan)],
        ).sealed()  # fmt: skip


def make_provider() -> OverlayImpactProvider:
    """Factory loaded lazily by `traceforge.regression.get_impact_provider("s15")`."""
    return OverlayImpactProvider()
