"""Four ways to rank candidate nodes for one failure: R0 ripgrep, trace-only, L, G.

Weights are fixed here BEFORE running on the faults and are not tuned to them.
"""

import math
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from index import Index, tokens

FRAME = re.compile(r'File "(.+?)", line (\d+), in (\S+)')
GRAPH_MAX_HOPS = 2


def trace_nodes(idx: Index, stderr: str) -> list[str]:
    """Project frames, innermost first, mapped to function nodes."""
    out = []
    for path, line, _fn in reversed(FRAME.findall(stderr)):
        p = Path(path)
        if p.parent.resolve() != idx.root.resolve():
            continue  # stdlib / site-packages frame
        nid = idx.node_at(p.name, int(line))
        if nid and nid not in out:
            out.append(nid)
    return out


def query_terms(idx: Index, stderr: str) -> list[str]:
    last = [ln for ln in stderr.strip().splitlines() if ln.strip()][-1]
    words = tokens(last)
    for nid in trace_nodes(idx, stderr):
        words += tokens(nid.split("::")[1]) + tokens(Path(idx.nodes[nid].path).stem)
    return list(dict.fromkeys(words))


def grep_terms(idx: Index, stderr: str) -> list[str]:
    """What a person would grep: raw function names from the trace + words (>2 chars) of the error."""
    last = [ln for ln in stderr.strip().splitlines() if ln.strip()][-1]
    words = [w for w in re.split(r"[^A-Za-z0-9_]+", last) if len(w) > 2]
    names = [nid.split("::")[1] for nid in trace_nodes(idx, stderr)]
    return list(dict.fromkeys(names + words))


def rank_ripgrep(idx: Index, terms: list[str]) -> list[str]:
    """R0: case-insensitive fixed-string search (substring, like `rg -i`), nodes ranked by hit count."""
    rg = shutil.which("rg")
    if rg is None:
        raise SystemExit(
            "ripgrep not found: winget install BurntSushi.ripgrep.MSVC, then open a new terminal"
        )
    args = [rg, "--no-heading", "-n", "-i", "-F"]
    for t in terms:
        args += ["-e", t]
    res = subprocess.run([*args, "."], cwd=idx.root, capture_output=True, text=True)
    hits: Counter[str] = Counter()
    for line in res.stdout.splitlines():
        m = re.match(r"(?:\./|\.\\)?([^:]+):(\d+):", line)
        if m:
            nid = idx.node_at(m.group(1), int(m.group(2)))
            if nid:
                hits[nid] += 1
    return [n for n, _ in sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))]


def bm25(idx: Index, terms: list[str], k1: float = 1.5, b: float = 0.75) -> dict[str, float]:
    docs = {nid: tokens(n.id + " " + n.text) for nid, n in idx.nodes.items()}
    avg = sum(map(len, docs.values())) / len(docs)
    df = Counter(t for d in docs.values() for t in set(d))
    scores = {}
    for nid, d in docs.items():
        tf = Counter(d)
        s = 0.0
        for t in terms:
            if tf[t]:
                idf = math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avg))
        scores[nid] = s
    return scores


def _order(scores: dict[str, float]) -> list[str]:
    return [n for n, s in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])) if s > 0]


def rank_trace_only(idx: Index, stderr: str) -> list[str]:
    return trace_nodes(idx, stderr)


def rank_lexical(idx: Index, stderr: str, terms: list[str]) -> list[str]:
    """L: trace anchors first (innermost first), then BM25."""
    anchors = trace_nodes(idx, stderr)
    rest = [n for n in _order(bm25(idx, terms)) if n not in anchors]
    return anchors + rest


def rank_graph(idx: Index, stderr: str, terms: list[str]) -> list[str]:
    """G: same anchors as L; others scored by normalized BM25 + 1/(1+hops) within 2 hops of an anchor."""
    anchors = trace_nodes(idx, stderr)
    raw = bm25(idx, terms)
    top = max(raw.values()) or 1.0
    dist = idx.hops(set(anchors), GRAPH_MAX_HOPS)
    scores = {}
    for nid in idx.nodes:
        if nid in anchors:
            continue
        s = raw[nid] / top
        if nid in dist:
            s += 1 / (1 + dist[nid])
        scores[nid] = s
    return anchors + _order(scores)
