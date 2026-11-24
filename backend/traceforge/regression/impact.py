"""ImpactProvider protocol, ImpactReport model (design 6.1) and the default graph-based provider.

`GraphImpactProvider` is built on the existing codeintel (`impact_set`, `changed_symbols`,
`signature_changes`). It builds graphs of the pre- and post-patch trees and then DROPS every node
whose path matches a hidden path pattern, and every test that is not a known visible test, so the
hidden suite can never appear in the report or in a selection.
"""

from __future__ import annotations

import fnmatch
import hashlib
import importlib
import json
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from traceforge.codeintel import build_graph
from traceforge.codeintel.config import UNKNOWN_PREFIX
from traceforge.codeintel.graph import Graph
from traceforge.codeintel.queries import changed_symbols, impact_set, signature_changes

EvidenceClass = Literal["static", "observed", "inferred", "unknown"]
LIMITATION = (
    "Dependants are those found by static analysis; absence is not evidence of none. "
    "Dynamic dispatch, reflection, monkeypatching and unseen contracts are not analysed."
)
MAX_DEPTH = 3
INFERRED_BELOW = 0.85  # edge confidence under this is an inferred (weak static) link
CONFIG_VIA = ("read_by", "declared_by", "env_of")


class ChangedSymbol(BaseModel):
    id: str
    change: Literal["added", "removed", "body", "signature", "seed"]
    path: str | None = None
    old_signature: str | None = None
    new_signature: str | None = None


class Dependant(BaseModel):
    id: str
    depth: int
    path: list[str]
    via: str
    evidence_class: EvidenceClass
    breaking: bool = False
    file: str | None = None


class ConfigConsumer(BaseModel):
    config_key: str
    consumer: str
    depth: int
    evidence_class: EvidenceClass


class RelatedTest(BaseModel):
    test_id: str  # visible test id as the graph reports it (no "test:" prefix)
    file: str | None = None
    depth: int
    direct: bool
    path: list[str]
    evidence_class: EvidenceClass
    rank: int


class RiskFlag(BaseModel):
    code: str
    subject: str
    detail: str


class NotAnalysable(BaseModel):
    subject: str
    reason: str


class ImpactReport(BaseModel):
    schema_version: int = 1
    provider: str = "graph"
    modified_files: list[str] = Field(default_factory=list)
    modified_symbols: list[ChangedSymbol] = Field(default_factory=list)
    direct_dependants: list[Dependant] = Field(default_factory=list)
    transitive_dependants: list[Dependant] = Field(default_factory=list)
    config_consumers: list[ConfigConsumer] = Field(default_factory=list)
    related_tests: list[RelatedTest] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    not_analysable: list[NotAnalysable] = Field(default_factory=list)
    limitation: str = LIMITATION
    impact_sha256: str = ""

    def canonical_json(self) -> str:
        d = self.model_dump(mode="json", exclude={"impact_sha256"})
        return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def compute_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def sealed(self) -> ImpactReport:
        return self.model_copy(update={"impact_sha256": self.compute_hash()})

    def verify(self) -> bool:
        return self.impact_sha256 == self.compute_hash()


@runtime_checkable
class ImpactProvider(Protocol):
    """Stable interface (also for P5-S15). Must be deterministic, offline, zero tokens, and must
    never return a hidden test or a hidden path. `visible_tests` are the only selectable tests."""

    name: str

    def analyse(
        self,
        base_root: str | Path,
        patched_root: str | Path,
        *,
        visible_tests: Sequence[str],
        hidden_paths: Sequence[str] = (),
        seeds: Sequence[str] = (),
    ) -> ImpactReport: ...


# ---- registry -------------------------------------------------------------------------------
_REGISTRY: dict[str, Callable[[], ImpactProvider]] = {}
S15_MODULE = "traceforge.analysis.impact_report"  # Rafique's module; factory `make_provider()`


def register_impact_provider(name: str, factory: Callable[[], ImpactProvider]) -> None:
    _REGISTRY[name] = factory


def get_impact_provider(name: str = "graph") -> ImpactProvider:
    if name == "s15" and name not in _REGISTRY:
        try:
            mod = importlib.import_module(S15_MODULE)
        except ImportError as e:
            raise KeyError("impact provider 's15' unavailable: module not present") from e
        register_impact_provider("s15", mod.make_provider)
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise KeyError(f"unknown impact provider {name!r}; known: {sorted(_REGISTRY)}") from None


# ---- default provider -----------------------------------------------------------------------
def is_hidden_path(path: str | None, hidden_paths: Iterable[str]) -> bool:
    if not path:
        return False
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    for pat in hidden_paths:
        pat = pat.replace("\\", "/").strip("/")
        if pat and (p == pat or p.startswith(pat + "/") or fnmatch.fnmatch(p, pat)):
            return True
    return False


def _strip(nid: str) -> str:
    return nid[5:] if nid.startswith("test:") else nid


class GraphImpactProvider:
    name = "graph"

    def __init__(self, max_depth: int = MAX_DEPTH) -> None:
        self.max_depth = max_depth

    def analyse(
        self,
        base_root: str | Path,
        patched_root: str | Path,
        *,
        visible_tests: Sequence[str],
        hidden_paths: Sequence[str] = (),
        seeds: Sequence[str] = (),
    ) -> ImpactReport:
        old = build_graph(base_root, "base", cache_dir=None)
        new = build_graph(patched_root, "patched", cache_dir=None)
        hid, vis = list(hidden_paths), set(visible_tests)
        sigs = signature_changes(old, new)

        def path_of(nid: str) -> str | None:
            for g in (new, old):
                if nid in g:
                    return g.node(nid).get("path")
            return None

        def selectable(nid: str, g: Graph) -> bool:
            p = g.node(nid).get("path")
            return not is_hidden_path(p, hid) and (_strip(nid) in vis or p in vis)

        changed = [c for c in changed_symbols(old, new) if not is_hidden_path(path_of(c), hid)]
        prod_changed = [c for c in changed if not c.startswith("test:")]
        seed_ids = sorted(set(prod_changed) | {s for s in seeds if s in new or s in old})
        sig_set = {c for c in seed_ids if c in sigs}
        iset = impact_set(new, [s for s in seed_ids if s in new], sig_set, self.max_depth)
        removed = [c for c in prod_changed if c not in new and c in old]
        old_iset = impact_set(old, removed, set(removed), self.max_depth) if removed else None

        modified: list[ChangedSymbol] = []
        for c in seed_ids:
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

        deps, tests, cfg = self._entries(new, iset, seed_ids, selectable, hid)
        if old_iset is not None:
            d2, t2, c2 = self._entries(old, old_iset, removed, selectable, hid)
            have = {d.id for d in deps}
            deps += [d for d in d2 if d.id not in have and d.id not in changed]
            have_t = {t.test_id for t in tests}
            tests += [t for t in t2 if t.test_id not in have_t]
            cfg += c2
        deps.sort(key=lambda d: (d.depth, d.id))
        direct = [d for d in deps if d.depth == 1]
        trans = [d for d in deps if d.depth > 1]
        tests.sort(key=lambda t: (t.depth, t.test_id))
        tests = [t.model_copy(update={"rank": i + 1}) for i, t in enumerate(tests)]
        cfg.sort(key=lambda c: (c.config_key, c.depth, c.consumer))

        flags: list[RiskFlag] = []
        notan: list[NotAnalysable] = []
        seed_set = set(seed_ids)
        for m in modified:
            outside = [
                d for d in direct
                if d.path[0] == m.id and d.id not in seed_set and d.via == "called_by"
            ]  # fmt: skip
            if m.change == "signature" and outside:
                flags.append(RiskFlag(
                    code="signature_change_external_callers", subject=m.id,
                    detail=f"{len(outside)} caller(s) outside the patch: "
                    + ", ".join(d.id for d in outside[:5]),
                ))  # fmt: skip
            if m.change == "removed" and outside:
                flags.append(RiskFlag(
                    code="removed_symbol_still_referenced", subject=m.id,
                    detail=", ".join(d.id for d in outside[:5]),
                ))  # fmt: skip
            if m.change in ("body", "signature", "added"):
                notan.append(NotAnalysable(
                    subject=m.id,
                    reason="contract changes the graph cannot see "
                    "(return type, raised exception, side effect)",
                ))  # fmt: skip
            if m.id in new:
                for _u, v, e in new.nx.out_edges(m.id, data=True):
                    if not e["reverse"] and v.startswith(UNKNOWN_PREFIX):
                        notan.append(NotAnalysable(
                            subject=f"{m.id} -> {v}", reason="unknown call site / dynamic dispatch"
                        ))  # fmt: skip
        for key in sorted({c.config_key for c in cfg}):
            n = sum(1 for c in cfg if c.config_key == key)
            flags.append(RiskFlag(
                code="config_key_read_elsewhere", subject=key, detail=f"{n} consumer(s)"
            ))  # fmt: skip
        blind = "no test coverage: this check is blind here"
        for m in modified:
            if m.change != "seed" and not any(m.id in t.path for t in tests):
                notan.append(NotAnalysable(subject=m.id, reason=blind))
        for d in direct:
            if not any(d.id in t.path for t in tests):
                notan.append(NotAnalysable(subject=d.id, reason=blind))
        flags.sort(key=lambda f: (f.code, f.subject))
        uniq: dict[tuple[str, str], NotAnalysable] = {}
        for n in notan:
            uniq[(n.subject, n.reason)] = n
        return ImpactReport(
            provider=self.name, modified_files=files, modified_symbols=modified,
            direct_dependants=direct, transitive_dependants=trans, config_consumers=cfg,
            related_tests=tests, risk_flags=flags,
            not_analysable=[uniq[k] for k in sorted(uniq)],
        ).sealed()  # fmt: skip

    def _entries(self, graph: Graph, iset, roots: Sequence[str], selectable, hid):
        parent: dict[str, str] = {}
        conf: dict[str, float] = {}
        depth: dict[str, int] = {r: 0 for r in roots if r in graph}
        order = sorted(iset.entries, key=lambda e: (e.depth, e.node))
        for e in order:
            best = None
            for p in sorted(n for n, d in depth.items() if d == e.depth - 1):
                for _u, v, data in graph.nx.out_edges(p, data=True):
                    if v == e.node and data["reverse"] and data["type"] == e.via:
                        best = (p, data.get("confidence", 1.0))
                        break
                if best:
                    break
            if best is None:
                continue
            parent[e.node], depth[e.node] = best[0], e.depth
            conf[e.node] = min(conf.get(best[0], 1.0), best[1])
        deps: list[Dependant] = []
        tests: list[RelatedTest] = []
        cfgs: list[ConfigConsumer] = []
        for e in order:
            if e.node not in parent:
                continue
            chain = [e.node]
            while chain[-1] in parent:
                chain.append(parent[chain[-1]])
            chain.reverse()
            if e.node.startswith(UNKNOWN_PREFIX):
                cls: EvidenceClass = "unknown"
            else:
                cls = "inferred" if conf[e.node] < INFERRED_BELOW else "static"
            nd = graph.node(e.node)
            p = nd.get("path")
            if is_hidden_path(p, hid) or any(
                is_hidden_path(graph.node(c).get("path"), hid) for c in chain
            ):
                continue
            if nd["kind"] == "test":
                if selectable(e.node, graph):
                    tests.append(RelatedTest(
                        test_id=_strip(e.node), file=p, depth=e.depth, direct=e.depth == 1,
                        path=[_strip(c) for c in chain], evidence_class=cls, rank=0,
                    ))  # fmt: skip
                continue
            if nd["kind"] == "file":
                continue  # importing files are leaves, not dependants
            deps.append(Dependant(
                id=e.node, depth=e.depth, path=chain, via=e.via, evidence_class=cls,
                breaking=e.breaking, file=p,
            ))  # fmt: skip
            if e.via in CONFIG_VIA and chain[0].startswith("cfg:"):
                cfgs.append(ConfigConsumer(
                    config_key=chain[0], consumer=e.node, depth=e.depth, evidence_class=cls
                ))  # fmt: skip
        return deps, tests, cfgs


register_impact_provider("graph", GraphImpactProvider)
