"""Evidence -> retrieval query and anchors (shared by both arms and both baselines).

Anchors (design fix D10, D32):
- the innermost `FORCED_FRAMES` (2) project frames, mapped with `symbol_at()`: forced inclusion;
- remaining project frames: ordinary candidates with a half-strength anchor bonus;
- config keys literally named in log / trace / health / issue evidence (never in the effective
  config or compose dump, which lists every key): forced, at most `MAX_CONFIG_ANCHORS`.
"""

import re
from dataclasses import dataclass, field

from traceforge.codeintel import Graph, symbol_at
from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem
from traceforge.evidence.traces import parse_tracebacks
from traceforge.retrieval.lexical import tokenize

FORCED_FRAMES = 2
MAX_CONFIG_ANCHORS = 3
MAX_QUERY_LINES = 40
_SIGNAL = re.compile(
    r"error|exception|fail|refused|timeout|timed out|critical|warn|unhealthy|invalid|denied|"
    r"unreachable|not found|traceback",
    re.I,
)
_NAMING_KINDS = ("log", "trace_frame", "health", "issue")
_TB_FRAME = re.compile(r'^\s*File "')


@dataclass(frozen=True)
class Anchor:
    node_id: str  # graph id
    source: str  # trace | trace_other | config
    rank: int  # order among forced anchors (0 = first)
    evidence_id: str
    forced: bool

    @property
    def strength(self) -> float:
        return 0.5 if self.source == "trace_other" else 1.0


@dataclass
class Query:
    service: str
    terms: list[str]  # BM25 query tokens
    grep_terms: list[str]  # raw fixed strings for the R0 baseline
    anchors: list[Anchor] = field(default_factory=list)
    trace_nodes: list[str] = field(default_factory=list)  # all project frames, innermost first


def _graph_path(graph: Graph, path: str) -> str | None:
    """Repo-relative graph file for a printed path: exact, else the longest path-suffix match."""
    p = path.replace("\\", "/")
    files = sorted(d["path"] for _n, d in graph.nx.nodes(data=True) if d["kind"] == "file")
    if p in files:
        return p
    hits = [f for f in files if p.endswith("/" + f) or f.endswith("/" + p)]
    return max(hits, key=len) if hits else None


def _frames(graph: Graph, items: list[EvidenceItem]) -> list[tuple[str, str]]:
    """(graph node id, evidence id) of project frames in printed order (outermost first)."""
    out: list[tuple[str, str]] = []
    structured = [i for i in items if i.kind == "trace_frame" and i.path and i.line]
    for i in structured:
        nid = symbol_at(graph, i.path, i.line)
        if nid:
            out.append((nid, i.id))
    if out:
        return out
    for i in items:  # fall back: tracebacks printed inside log text
        for tb in parse_tracebacks(i.content) if i.kind == "log" else []:
            for f in tb.frames:
                rel = _graph_path(graph, f.path)
                nid = symbol_at(graph, rel, f.line) if rel else None
                if nid:
                    out.append((nid, i.id))
    return out


def _signal_lines(items: list[EvidenceItem]) -> list[str]:
    lines: list[str] = []
    for i in items:
        if i.kind == "issue":
            lines += [ln for ln in i.content.splitlines() if ln.strip()][:10]
        elif i.kind in ("log", "health"):
            lines += [
                ln.strip()
                for ln in i.content.splitlines()
                if _SIGNAL.search(ln) and not _TB_FRAME.match(ln)
            ]
        elif i.kind == "trace_frame":
            lines += [ln.strip() for ln in i.content.splitlines() if not _TB_FRAME.match(ln)]
    return list(dict.fromkeys(lines))[:MAX_QUERY_LINES]


def _config_anchors(graph: Graph, items: list[EvidenceItem], start_rank: int) -> list[Anchor]:
    keys = {d["name"]: n for n, d in graph.nx.nodes(data=True) if d["kind"] == "config_key"}
    found: list[tuple[int, int, str, str, str]] = []
    for i in (i for i in items if i.kind in _NAMING_KINDS):
        for key, nid in keys.items():
            m = re.search(rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])", i.content)
            if m:
                found.append((int(i.id[3:]), m.start(), key, nid, i.id))
    found.sort()
    seen: list[Anchor] = []
    for _e, _pos, _key, nid, eid in found:
        if nid not in [a.node_id for a in seen] and len(seen) < MAX_CONFIG_ANCHORS:
            seen.append(Anchor(nid, "config", start_rank + len(seen), eid, True))
    return seen


def build_query(evidence: EvidenceBundle, graph: Graph, service: str = "") -> Query:
    items = list(evidence.items)
    service = service or next((i.service for i in items), "")
    frames = _frames(graph, items)[::-1]  # innermost first
    nodes: list[str] = []
    eids: dict[str, str] = {}
    for nid, eid in frames:
        if nid not in nodes:
            nodes.append(nid)
            eids[nid] = eid
    anchors = [
        Anchor(n, "trace" if r < FORCED_FRAMES else "trace_other", r, eids[n], r < FORCED_FRAMES)
        for r, n in enumerate(nodes)
    ]
    anchors += _config_anchors(graph, items, FORCED_FRAMES)
    lines = _signal_lines(items)
    names = [graph.node(n)["qualname"] for n in nodes]
    terms = " ".join([service, *lines, *names])
    err = [ln for ln in lines if _SIGNAL.search(ln)][:3]
    last = names[0].rsplit(".", 1)[-1:] if names else []
    words = [w for ln in err for w in re.split(r"[^A-Za-z0-9_]+", ln) if len(w) > 2]
    grep = list(dict.fromkeys([*[n.rsplit(".", 1)[-1] for n in names], *last, *words]))
    return Query(service, tokenize(terms), grep, anchors, nodes)
