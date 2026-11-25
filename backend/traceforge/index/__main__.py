# ruff: noqa: E501
"""CLI: python -m traceforge.index {sync,verify} --repo R --namespace-root D [--model M] [--fake]"""

import argparse
import json
import sys
import time
from pathlib import Path

from traceforge.codeintel import build_graph
from traceforge.retrieval.corpus import build_corpus

from . import EmbeddingIndex, FakeEmbedder, OllamaEmbedder, verify


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="traceforge.index")
    ap.add_argument("cmd", choices=["sync", "verify", "gc"])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--namespace-root", required=True)
    ap.add_argument("--model", default="all-minilm:22m")
    ap.add_argument("--commit", default=None)
    ap.add_argument("--fake", action="store_true", help="offline FakeEmbedder (testing)")
    ap.add_argument("--batch-size", type=int, default=32)
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    graph = build_graph(Path(a.repo), cache_dir=None)
    chunks = build_corpus(graph).chunks
    t_graph = time.perf_counter() - t0
    emb = FakeEmbedder(dims=384) if a.fake else OllamaEmbedder(a.model, batch_size=a.batch_size)
    idx = EmbeddingIndex(a.namespace_root, emb, a.batch_size)
    if a.cmd == "sync":
        rep = idx.sync(chunks, graph, a.commit or graph.base_sha)
        print(
            json.dumps(
                {
                    **rep.as_dict(),
                    "chunks": len(chunks),
                    "graph_corpus_seconds": round(t_graph, 3),
                    "storage_bytes": idx.store.storage_bytes(),
                    "namespace": str(idx.store.dir),
                },
                indent=1,
            )
        )
        return 0
    if a.cmd == "gc":
        print(json.dumps({"removed": idx.gc("active")}))
        return 0
    problems = verify(idx, chunks, graph)
    print(json.dumps({"ok": not problems, "problems": problems}, indent=1))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
