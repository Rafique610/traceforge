# ruff: noqa: E501
"""RepoContext: the repository as a retriever sees it (graph + chunk corpus built by the existing
`traceforge.codeintel` / `traceforge.retrieval.corpus` libraries, read-only)."""

from __future__ import annotations

import hashlib
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from traceforge.codeintel import Graph, build_graph
from traceforge.contracts.evidence import EvidenceBundle, EvidenceItem
from traceforge.retrieval import corpus as corpus_mod
from traceforge.retrieval.anchors import _signal_lines, build_query, symptom_terms
from traceforge.retrieval.corpus import Corpus, get_corpus
from traceforge.retrieval.lexical import index_for
from traceforge.retrieval_bench.types import QueryText

FORBIDDEN_PARTS = ("hidden_tests", ".git", "mutation.patch")


@dataclass
class RepoContext:
    name: str
    root: Path
    graph: Graph
    corpus: Corpus
    build_s: float = 0.0
    graph_s: float = 0.0
    corpus_s: float = 0.0
    bm25_s: float = 0.0
    state: dict[str, Any] = field(default_factory=dict)  # per-method prepared indexes

    @property
    def n_chunks(self) -> int:
        return len(self.corpus.chunks)

    def n_files(self) -> int:
        return len({c.path for c in self.corpus.chunks})

    def corpus_text_bytes(self) -> int:
        return sum(len(c.text.encode("utf-8")) for c in self.corpus.chunks)

    def make_query(self, qid: str, text: str, service: str = "") -> QueryText:
        """Free-text query -> QueryText with a synthetic evidence bundle (one `issue` item; plus a
        `log` item when the text contains a traceback, so printed frames become trace anchors)."""
        return QueryText(text, qid, synth_evidence(qid, text, service), service)


def synth_evidence(qid: str, text: str, service: str = "") -> EvidenceBundle:
    def item(n: int, kind: str, content: str) -> EvidenceItem:
        return EvidenceItem(
            id=f"EV-{n:04d}", kind=kind, service=service, content=content,  # type: ignore[arg-type]
            sha256=hashlib.sha256(content.encode()).hexdigest(),
        )  # fmt: skip

    items = [item(1, "issue", text)]
    if "Traceback (most recent call last)" in text:
        items.append(item(2, "log", text))
    return EvidenceBundle(
        incident_id=qid or "q", base_sha="0" * 40, compose_sha256="0" * 64, items=items
    )


def build_context(name: str, root: Path) -> RepoContext:
    """Cold build (graph, corpus, BM25), timed per stage. Clears the in-process corpus cache first
    so the timings are real builds."""
    corpus_mod._CACHE.clear()
    t0 = time.perf_counter()
    graph = build_graph(Path(root), cache_dir=None)
    t1 = time.perf_counter()
    corpus = get_corpus(graph)
    t2 = time.perf_counter()
    index_for(corpus)
    t3 = time.perf_counter()
    return RepoContext(name, Path(root), graph, corpus, t3 - t0, t1 - t0, t2 - t1, t3 - t2)


def measure_build_peak_bytes(root: Path) -> int:
    """Peak Python heap (tracemalloc) of a cold graph+corpus+BM25 build."""
    corpus_mod._CACHE.clear()
    tracemalloc.start()
    try:
        g = build_graph(Path(root), cache_dir=None)
        index_for(get_corpus(g))
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def query_text_from_evidence(graph: Graph, ev: EvidenceBundle, service: str = "") -> str:
    """The text the existing BM25 query is built from (service + signal lines + frame names +
    symptom terms), before tokenizing: the plain-string query for dense arms on the dev split."""
    from traceforge.agent.symptom import symptom_view

    q = build_query(ev, graph, service)
    names = [graph.node(n)["qualname"] for n in q.trace_nodes]
    svc = service or next((i.service for i in ev.items), "")
    return " ".join([svc, *_signal_lines(list(ev.items)), *names, *symptom_terms(symptom_view(ev))])


def process_peak_rss_mb() -> float | None:
    """Peak working set of this process (Windows ctypes; ru_maxrss elsewhere; else None)."""
    try:
        import ctypes
        from ctypes import wintypes

        names = (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
            "PagefileUsage", "PeakPagefileUsage",
        )  # fmt: skip

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in names
            ]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32, ps = ctypes.windll.kernel32, ctypes.windll.psapi  # type: ignore[attr-defined]
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        ps.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
        ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return round(pmc.PeakWorkingSetSize / 1e6, 1)
    except Exception:
        try:
            import resource

            return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
        except Exception:
            return None
