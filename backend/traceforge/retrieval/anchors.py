"""Evidence -> retrieval query and anchors (shared by both arms and both baselines).

Anchors (design fix D10, D32):
- the innermost `FORCED_FRAMES` (2) project frames, mapped with `symbol_at()`: forced inclusion;
- remaining project frames: ordinary candidates with a half-strength anchor bonus;
- config keys literally named in log / trace / health / issue evidence (never in the effective
  config or compose dump, which lists every key): forced, at most `MAX_CONFIG_ANCHORS`.
"""

import re
from dataclasses import dataclass, field

from traceforge.agent.symptom import SymptomView, symptom_view
from traceforge.codeintel import Graph, symbol_at
from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem
from traceforge.evidence.traces import parse_tracebacks
from traceforge.retrieval.lexical import tokenize
from traceforge.retrieval.routes import match_routes

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
    source: str  # trace | trace_other | config | symptom_test | symptom_route | symptom_config
    rank: int  # order among forced anchors (0 = first)
    evidence_id: str
    forced: bool
    weight: float = 1.0  # scales the base strength (symptom anchors: share of failing tests)

    @property
    def strength(self) -> float:
        base = {
            "trace_other": 0.5,
            "symptom_test": 0.6,
            "symptom_route": 0.8,
            "symptom_config": SYMPTOM_CONFIG_STRENGTH,
        }.get(self.source, 1.0)
        return base * self.weight


@dataclass
class Query:
    service: str
    terms: list[str]  # BM25 query tokens
    grep_terms: list[str]  # raw fixed strings for the R0 baseline
    anchors: list[Anchor] = field(default_factory=list)
    trace_nodes: list[str] = field(default_factory=list)  # all project frames, innermost first
    # Symptom-derived anchors that use graph relations (tests_covers, route resolution). Only the
    # G arm uses them, so G - L measures what the graph adds; the symptom TERMS are in both arms.
    graph_anchors: list[Anchor] = field(default_factory=list)


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
        if i.kind == "issue" and i.content.startswith("SYMPTOM"):
            continue  # symptom items feed the query through symptom_terms (no boilerplate)
        if i.kind == "issue" and i.content.startswith("FINDING"):
            # a deterministic hint: its sentence names keys and hosts; drop the tag/rule prefix
            head = re.sub(r"^FINDING \[\w+\] ", "", i.content.splitlines()[0])
            lines.append(re.sub(r" \(evidence: [^)]*\)$", "", head))
        elif i.kind == "issue":
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


_BOILER = frozenset(
    "symptom failing test visible reproducer suite compared left right produced code under "
    "required request made check detail summary base commit runs failed passed".split()
)
_NOISE = frozenset("assert true false none".split())
MAX_SYMPTOM_ANCHORS = 8
MAX_SYMPTOM_CONFIG = 6
SYMPTOM_CONFIG_STRENGTH = 0.5


def symptom_terms(view: SymptomView) -> list[str]:
    """Query words from the symptom: endpoint path/query words, test names, the assertion's
    identifiers and detail text. Pure numbers and the symptom boilerplate are dropped."""
    words: list[str] = []
    for _meth, path in view.requests:
        words += [w for w in re.split(r"[^A-Za-z0-9_]+", path) if w and not w.isdigit()]
    for text in view.texts:
        for ln in text.splitlines()[1:]:  # first line is the tag
            if ln.startswith("compared:"):
                ln = ln.split(" (left")[0]
            words += re.findall(r"[A-Za-z_][A-Za-z0-9_]*", ln)
    for _suite, tid in view.tests:
        words += re.findall(r"[A-Za-z_][A-Za-z0-9_]*", tid)
    out: list[str] = []
    for w in words:
        if w.lower() in _BOILER or w.lower() in _NOISE:
            continue
        out.append(w)  # repeats kept on purpose: a word in every failing test weighs more
    return out


def _test_nodes(graph: Graph, test_id: str) -> list[str]:
    path, _, name = test_id.partition("::")
    name = name.split("[")[0]
    path = path.replace("\\", "/")
    out = []
    for nid, d in graph.nx.nodes(data=True):
        if d.get("kind") != "test" or d.get("qualname", "").rsplit(".", 1)[-1] != name:
            continue
        gp = d.get("path", "")
        if gp == path or gp.endswith("/" + path) or path.endswith("/" + gp):
            out.append(nid)
    return out


def symptom_anchors(graph: Graph, view: SymptomView, evidence_id: str) -> list[Anchor]:
    """Graph anchors from a symptom, general and read-only:
    - symptom_test: functions covered (`tests_covers`) by the failing visible tests; a function
      covered by more of the failing tests is a stronger suspect (weight = share of failing tests);
    - symptom_route: the handler of each HTTP request the failing tests made."""
    anchors: list[Anchor] = []
    covered: dict[str, int] = {}
    failing = [tid for suite, tid in view.tests if suite == "visible"]
    for tid in failing:
        seen: set[str] = set()
        for tn in _test_nodes(graph, tid):
            for _u, v, d in graph.nx.out_edges(tn, data=True):
                kind = graph.node(v)["kind"] if v in graph else "unknown"
                if (
                    d["type"] == "tests_covers"
                    and kind in ("function", "method", "class")
                    and v not in seen
                ):
                    seen.add(v)
                    covered[v] = covered.get(v, 0) + 1
    for rank, (nid, n) in enumerate(sorted(covered.items(), key=lambda x: (-x[1], x[0]))):
        if rank >= MAX_SYMPTOM_ANCHORS:
            break
        anchors.append(
            Anchor(nid, "symptom_test", rank, evidence_id, False, n / max(1, len(failing)))
        )
    seen_nodes = {a.node_id for a in anchors}
    for meth, path in view.requests:
        for r in match_routes(graph, meth, path)[:1]:
            if r.node_id not in seen_nodes:
                seen_nodes.add(r.node_id)
                anchors.append(Anchor(r.node_id, "symptom_route", len(anchors), evidence_id, False))
    return anchors + symptom_config_anchors(graph, view, anchors, evidence_id)


def _config_read_by(graph: Graph, nid: str) -> list[str]:
    return sorted(
        v
        for _u, v, d in graph.nx.out_edges(nid, data=True)
        if d["type"] == "reads_config" and v in graph and graph.node(v)["kind"] == "config_key"
    )


def symptom_config_anchors(
    graph: Graph, view: SymptomView, base: list[Anchor], evidence_id: str
) -> list[Anchor]:
    """Settings the failing path reads (G only). A wrong computed value is often a wrong setting,
    and the failing endpoint or test does not name it: the keys read by the anchored code (and by
    what it calls directly, one hop) are offered, those whose words occur in the symptom first.
    The anchors are not forced and weaker than route/test anchors; at most MAX_SYMPTOM_CONFIG."""
    words = {w.lower() for w in symptom_terms(view)}
    cands: dict[str, tuple[int, int, str]] = {}  # cfg node -> (term miss, call distance, key)
    for a in base:
        if a.node_id not in graph:
            continue
        near = [(a.node_id, 0)]
        near += [
            (v, 1)
            for _u, v, d in graph.nx.out_edges(a.node_id, data=True)
            if d["type"] == "calls"
            and v in graph
            and graph.node(v)["kind"] in ("function", "method")
        ]
        for fn, dist in near:
            for cfg in _config_read_by(graph, fn):
                key = graph.node(cfg)["name"]
                toks = [t for t in key.lower().split("_") if len(t) > 2]
                miss = 0 if any(t in words or t.rstrip("s") in words for t in toks) else 1
                cur = cands.get(cfg)
                if cur is None or (miss, dist) < cur[:2]:
                    cands[cfg] = (miss, dist, key)
    ranked = sorted(cands.items(), key=lambda kv: (kv[1], kv[0]))[:MAX_SYMPTOM_CONFIG]
    out: list[Anchor] = []
    for i, (cfg, _v) in enumerate(ranked):  # the key and the settings field that reads it
        nodes = sorted(
            v
            for _u, v, d in graph.nx.out_edges(cfg, data=True)
            if d["type"] == "read_by" and v in graph and graph.node(v)["kind"] == "settings_field"
        ) or [cfg]
        out += [Anchor(n, "symptom_config", i, evidence_id, False) for n in nodes]
    return out


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
    view = symptom_view(evidence)
    terms = " ".join([service, *lines, *names, *symptom_terms(view)])
    err = [ln for ln in lines if _SIGNAL.search(ln)][:3]
    last = names[0].rsplit(".", 1)[-1:] if names else []
    words = [w for ln in err for w in re.split(r"[^A-Za-z0-9_]+", ln) if len(w) > 2]
    grep = list(dict.fromkeys([*[n.rsplit(".", 1)[-1] for n in names], *last, *words]))
    g_anchors = symptom_anchors(graph, view, view.evidence_ids[0]) if view.evidence_ids else []
    return Query(service, tokenize(terms), grep, anchors, nodes, g_anchors)
