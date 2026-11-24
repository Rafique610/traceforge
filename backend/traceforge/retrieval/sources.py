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
SOURCE_SUFFIXES = (
    ".py",
    ".toml",
    ".ini",
    ".yaml",
)  # the files a patch may edit (see e2e.allowlist)


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

    def _source_path(self, case: CaseManifest, path: str) -> Path | None:
        """The real file for `path` if it is an editable source file of the case's own service."""
        parts = path.replace("\\", "/").split("/")
        ok = (
            len(parts) > 2
            and parts[:2] == ["lab", case.service]
            and ".." not in parts
            and ":" not in path
            and not any(p in _FORBIDDEN_PARTS or p == "tests" for p in parts)
            and path.endswith(SOURCE_SUFFIXES)
        )
        f = (self.repo / "/".join(parts)) if ok else None
        return (
            f if f is not None and f.is_file() and f.resolve().is_relative_to(self.repo) else None
        )

    def source_files(self, case: CaseManifest) -> list[str]:
        """Repo-relative paths of the editable source files of the case's service (sorted)."""
        base = self.repo / "lab" / case.service
        found = sorted(p.relative_to(self.repo).as_posix() for p in base.rglob("*") if p.is_file())
        return [p for p in found if self._source_path(case, p) is not None]

    def _symbols(self, case: CaseManifest) -> list[dict]:
        """Function/method/class nodes of the case's own editable source files (no tests)."""
        files = {p for p in self.source_files(case) if p.endswith(".py")}
        out = [
            d
            for _n, d in self.graph.nx.nodes(data=True)
            if d.get("kind") in ("function", "method", "class") and d.get("path") in files
        ]
        return sorted(out, key=lambda d: (d["path"], d["start"]))

    def workspace_index(self, case: CaseManifest, max_chars: int = 3500) -> str:
        """`path: symbol, symbol, ...` for every editable source file of the service, so the model
        can pick real paths and names instead of guessing (never lists tests or other services)."""
        by_file: dict[str, list[str]] = {}
        for d in self._symbols(case):
            by_file.setdefault(d["path"], []).append(d["qualname"])
        lines, used = [], 0
        for path, names in by_file.items():
            ln = f"{path}: " + ", ".join(names)
            ln = ln if len(ln) <= 400 else ln[:397] + "..."
            if used + len(ln) > max_chars:
                lines.append(f"{path}: (symbols omitted; use search_code)")
                continue
            lines.append(ln)
            used += len(ln)
        return "\n".join(lines)

    def search_code(self, case: CaseManifest, query: str, limit: int = 8) -> list[str]:
        """Symbols of the service whose name, path or docstring share words with `query`,
        best first, as `path::qualname (lines a-b)`. Deterministic; the service workspace only."""
        from traceforge.retrieval.lexical import tokenize

        want = set(tokenize(query))
        scored = []
        for d in self._symbols(case):
            names = set(tokenize(d["qualname"] + " " + d["path"].rsplit("/", 1)[-1]))
            doc = set(tokenize(d.get("doc") or ""))
            score = 2 * len(want & names) + len(want & doc)
            if score:
                scored.append((-score, d["path"], d["start"], d))
        scored.sort(key=lambda x: x[:3])
        return [
            f"{d['path']}::{d['qualname']} (lines {d['start']}-{d['end']})"
            for *_k, d in scored[:limit]
        ]

    def read_file(self, case: CaseManifest, path: str) -> str | None:
        """Exact text of an editable source file: bytes decoded as UTF-8, no newline translation,
        no line numbers, nothing added. None if the path is not such a file."""
        f = self._source_path(case, path)
        try:
            return f.read_bytes().decode("utf-8") if f is not None else None
        except (OSError, UnicodeDecodeError):
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
