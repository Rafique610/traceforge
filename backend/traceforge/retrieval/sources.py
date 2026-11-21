"""RealContextSource: the agent's ContextSource protocol over a repo path and its code graph.

`retrieve` runs L or G (same budget and packer); `read_symbol` returns the real source of a symbol
from the repo tree; `neighbors` returns code-map neighbours from the real graph; `code_map` is the
same outline in every condition (D22). Ids accepted/returned follow the metrics convention
(`sym:<path>::<qualname>`, `test:...`, `cfg:<key>`); graph ids are accepted too.
"""

from pathlib import Path
from typing import Any

from traceforge.codeintel import Graph, build_graph, code_map, neighbors
from traceforge.contracts.case_manifest import CaseManifest
from traceforge.contracts.context import ContextBundle
from traceforge.contracts.evidence import EvidenceBundle
from traceforge.retrieval.corpus import get_corpus, graph_id_of
from traceforge.retrieval.retrieve import retrieve

_FORBIDDEN_PARTS = ("hidden_tests", ".git")


class RealContextSource:
    def __init__(self, repo_path: str | Path, graph: Graph | None = None) -> None:
        self.repo = Path(repo_path).resolve()
        self._graph = graph

    @property
    def graph(self) -> Graph:
        if self._graph is None:
            self._graph = build_graph(self.repo, cache_dir=None)
        return self._graph

    def retrieve(
        self, evidence: EvidenceBundle, graph: Any, mode: str, token_budget: int
    ) -> ContextBundle:
        g = graph if isinstance(graph, Graph) else self.graph
        return retrieve(evidence, g, mode, token_budget)

    def read_symbol(self, case: CaseManifest, path: str, qualname: str) -> str | None:
        """Source of `qualname` in `path` (repo-relative POSIX) with line numbers, else None."""
        parts = path.replace("\\", "/").split("/")
        if ".." in parts or ":" in path or any(p in _FORBIDDEN_PARTS for p in parts):
            return None
        g = self.graph
        for prefix in ("func", "class", "test", "field"):
            nid = f"{prefix}:{'/'.join(parts)}::{qualname}"
            if nid in g:
                d = g.node(nid)
                try:
                    lines = (
                        (self.repo / d["path"]).read_text("utf-8", errors="replace").splitlines()
                    )
                except OSError:
                    return None
                return "\n".join(
                    f"{i}: {lines[i - 1]}" for i in range(d["start"], min(d["end"], len(lines)) + 1)
                )
        return None

    def neighbors(self, node_id: str) -> list[str]:
        """Symbols/config keys/tests within 2 hops (hubs not expanded), nearest first."""
        g = self.graph
        nid = graph_id_of(node_id, g)
        if nid is None:
            return []
        corpus = get_corpus(g)
        return [
            corpus.by_node[n].hit_id
            for n, _h in neighbors(g, nid, hops=2, expand_hubs=False)
            if n in corpus.by_node
        ]

    def code_map(self) -> str:
        return code_map(self.graph)
