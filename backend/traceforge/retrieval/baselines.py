"""E1 baselines (D18): R0 ripgrep-style search and trace-only. Both output a ContextBundle packed
with the same budget/packer as L and G. ContextBundle.mode only allows L/G, so baselines are
stamped "L"; E1 keeps the real method name beside every saved bundle.

R0: fixed-string, case-insensitive, multi-term search; a line matches if any term occurs in it;
matching lines are credited to the function/test/config key that owns them and owners are ranked
by matching-line count (ties by id). Uses `rg` when installed (`rg -i -F -n -e term ...`),
otherwise a Python implementation with the same semantics (substring match per line, same files).
`r0_impl()` reports which one ran.
"""

import os
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from traceforge.codeintel import Graph
from traceforge.codeintel.config import SKIP_DIRS
from traceforge.contracts.context import ContextBundle
from traceforge.contracts.evidence import EvidenceBundle
from traceforge.retrieval.anchors import Query, build_query
from traceforge.retrieval.context_budget import Ranked, pack
from traceforge.retrieval.corpus import get_corpus, qualified_id

SEARCH_SUFFIXES = (".py", ".yaml", ".yml", ".env", ".toml", ".ini", ".cfg", ".json", ".txt", ".md")
MAX_FILE_BYTES = 1_000_000


def r0_impl() -> str:
    return "ripgrep" if shutil.which("rg") else "python-fixed-string"


def _files(repo: Path) -> list[str]:
    out = []
    for dirpath, dirs, names in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for n in sorted(names):
            p = Path(dirpath) / n
            if (
                n.endswith(SEARCH_SUFFIXES) or n.startswith(".env")
            ) and p.stat().st_size < MAX_FILE_BYTES:
                out.append(p.relative_to(repo).as_posix())
    return out


def _grep_python(repo: Path, terms: list[str]) -> list[tuple[str, int]]:
    low = [t.lower() for t in terms]
    hits = []
    for rel in _files(repo):
        try:
            text = (repo / rel).read_text("utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            ll = line.lower()
            if any(t in ll for t in low):
                hits.append((rel, i))
    return hits


def _grep_rg(repo: Path, terms: list[str], rg: str) -> list[tuple[str, int]]:
    args = [rg, "--no-heading", "-n", "-i", "-F", "--no-ignore", "--hidden", "-g", "!.git"]
    for t in terms:
        args += ["-e", t]
    res = subprocess.run([*args, "."], cwd=repo, capture_output=True, text=True, timeout=60)  # noqa: S603
    hits = []
    for line in res.stdout.splitlines():
        m = re.match(r"(?:\./|\.\\)?(.+?):(\d+):", line)
        if m:
            hits.append((m.group(1).replace("\\", "/"), int(m.group(2))))
    return hits


def grep_hits(repo: Path, terms: list[str]) -> list[tuple[str, int]]:
    rg = shutil.which("rg")
    return _grep_rg(repo, terms, rg) if rg else _grep_python(repo, terms)


def rank_r0(query: Query, graph: Graph) -> list[Ranked]:
    corpus = get_corpus(graph)
    count: Counter[str] = Counter()
    for path, line in grep_hits(graph.repo, query.grep_terms) if query.grep_terms else []:
        c = corpus.owner_at(path, line)
        if c is not None:
            count[c.node_id] += 1
    order = sorted(count.items(), key=lambda kv: (-kv[1], corpus.by_node[kv[0]].hit_id))
    return [
        Ranked(
            corpus.by_node[n],
            float(k),
            [f"{r0_impl()}:{k} matching lines"],
            hit_id=qualified_id(corpus.by_node[n], query.service),
        )
        for n, k in order
    ]


def rank_trace_only(query: Query, graph: Graph) -> list[Ranked]:
    corpus = get_corpus(graph)
    ranked = []
    for i, nid in enumerate(query.trace_nodes):
        c = corpus.by_node.get(nid)
        if c is not None:
            ranked.append(
                Ranked(
                    c,
                    1.0 / (i + 1),
                    [f"trace_frame#{i + 1}"],
                    hit_id=qualified_id(c, query.service),
                )
            )
    return ranked


def run_baseline(
    method: str, evidence: EvidenceBundle, graph: Graph, token_budget: int, service: str = ""
) -> ContextBundle:
    query = build_query(evidence, graph, service)
    ranked = {"R0": rank_r0, "trace_only": rank_trace_only}[method](query, graph)
    hits, used = pack(ranked, token_budget)
    return ContextBundle(
        incident_id=evidence.incident_id,
        mode="L",
        token_budget=token_budget,
        tokens_used=used,
        hits=hits,
    )
