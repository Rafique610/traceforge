"""build_graph(): scan a repo, (re)parse changed files, assemble a typed provenance graph."""

import hashlib
import os
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

from .assemble import assemble
from .cache import FactsCache, sha
from .compose_graph import dotenv_keys, is_compose, is_dotenv
from .config import REVERSE_OF, SKIP_DIRS, GraphConfig
from .python_ast import parse_python

DEFAULT_CACHE = Path(".cache/graph")


@dataclass
class Graph:
    repo: Path
    base_sha: str
    content_hash: str
    nx: nx.MultiDiGraph
    config: GraphConfig
    stats: dict = field(default_factory=dict)
    _adj: dict = field(default_factory=dict, repr=False)

    def adjacency(self, types: tuple[str, ...] | None = None) -> dict[str, list[str]]:
        """Undirected neighbour lists over forward edges of `types` (None = all), sorted.

        `unknown:` nodes are excluded. Cached per type set.
        """
        key = tuple(sorted(types)) if types else None
        if key not in self._adj:
            adj: dict[str, set[str]] = defaultdict(set)
            for u, v, d in self.nx.edges(data=True):
                if d["reverse"] or (key and d["type"] not in key):
                    continue
                if self.nx.nodes[u]["kind"] == "unknown" or self.nx.nodes[v]["kind"] == "unknown":
                    continue
                adj[u].add(v)
                adj[v].add(u)
            self._adj[key] = {n: sorted(s) for n, s in adj.items()}
        return self._adj[key]

    def node(self, nid: str) -> dict:
        return self.nx.nodes[nid]

    def __contains__(self, nid: str) -> bool:
        return nid in self.nx


def detect_sha(repo: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else "nogit"
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def scan(repo: Path, max_bytes: int) -> tuple[dict[str, bytes], dict[str, str], dict[str, str]]:
    """-> (python files rel->bytes, compose rel->text, dotenv rel->text). POSIX rel paths."""
    py, compose, dotenv = {}, {}, {}
    for dirpath, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            p = Path(dirpath) / name
            rel = p.relative_to(repo).as_posix()
            try:
                if p.is_symlink() or p.stat().st_size > max_bytes:
                    continue
                if name.endswith(".py"):
                    py[rel] = p.read_bytes()
                elif is_compose(name):
                    compose[rel] = p.read_text(encoding="utf-8", errors="replace")
                elif is_dotenv(name):
                    dotenv[rel] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return py, compose, dotenv


def _to_nx(b, cfg: GraphConfig) -> nx.MultiDiGraph:
    """Deterministic MultiDiGraph with reverse edges and hub-degree data."""
    g = nx.MultiDiGraph()
    forward = [(k, e) for k, e in sorted(b.edges.items()) if k[0] in b.nodes and k[1] in b.nodes]
    sem = set(cfg.distance_edge_types)
    deg: dict[str, set] = defaultdict(set)
    deg_all: dict[str, set] = defaultdict(set)
    for (u, v, t, _p), _e in forward:
        if b.nodes[u]["kind"] == "unknown" or b.nodes[v]["kind"] == "unknown":
            continue
        deg_all[u].add(v)
        deg_all[v].add(u)
        if t in sem:
            deg[u].add(v)
            deg[v].add(u)
    for nid in sorted(b.nodes):
        d = len(deg[nid])
        factor = 1.0 if d <= cfg.hub_degree_threshold else cfg.hub_degree_threshold / d
        g.add_node(nid, **b.nodes[nid], degree=d, degree_all=len(deg_all[nid]), hub_factor=factor)
    for (u, v, t, p), e in forward:
        g.add_edge(u, v, key=f"{t}@{p}", reverse=False, **e)
        g.add_edge(v, u, key=f"{REVERSE_OF[t]}@{p}", reverse=True, **{**e, "type": REVERSE_OF[t]})
    return g


def build_graph(
    repo_path: str | Path,
    base_sha: str | None = None,
    *,
    cache_dir: str | Path | None = DEFAULT_CACHE,
    config: GraphConfig | None = None,
) -> Graph:
    """Build the code/config graph of `repo_path`. cache_dir=None disables the disk cache."""
    t0 = time.perf_counter()
    cfg = config or GraphConfig()
    repo = Path(repo_path).resolve()
    base_sha = base_sha or detect_sha(repo)
    py, compose, dotenv = scan(repo, cfg.max_file_bytes)
    cache = FactsCache(Path(cache_dir), repo, base_sha) if cache_dir is not None else None
    facts, entries, parsed = {}, {}, 0
    for rel in sorted(py):
        digest = sha(py[rel])
        f = cache.get(rel, digest) if cache else None
        if f is None:
            f = parse_python(py[rel].decode("utf-8", errors="replace"))
            parsed += 1
        facts[rel] = f
        entries[rel] = {"sha": digest, "facts": f}
    if cache:
        cache.save(entries)
    t1 = time.perf_counter()
    b = assemble(repo, facts, compose, {r: dotenv_keys(t) for r, t in dotenv.items()}, cfg)
    g = _to_nx(b, cfg)
    h = hashlib.sha256(
        "".join(f"{r}={e['sha']};" for r, e in entries.items()).encode()
        + "".join(
            f"{r}={sha(t.encode())};" for r, t in sorted({**compose, **dotenv}.items())
        ).encode()
    ).hexdigest()
    graph = Graph(repo, base_sha, h, g, cfg)
    graph.stats = {
        "python_files": len(py),
        "reparsed": parsed,
        "from_cache": len(py) - parsed,
        "syntax_errors": sum(1 for f in facts.values() if f["error"]),
        "parse_seconds": t1 - t0,
        "assemble_seconds": time.perf_counter() - t1,
        "total_seconds": time.perf_counter() - t0,
    }
    return graph
