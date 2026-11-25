# ruff: noqa: E501
"""Flat numpy cosine search over the live manifest, and the index consistency verifier.

search(index, query_vec, k) -> list[SearchHit(id, score, path, kind)]
    Query is L2-normalised; score = dot product (cosine). Ordering is by score descending
    (scores rounded to 6 decimals for comparison) then chunk id ascending: fully deterministic.
verify(index, chunks) -> list[str] of problems ([] means consistent). Checks: ACTIVE pointer
    and manifest hash valid; no duplicate ids; every live chunk has a finite vector of the
    namespace dims whose checksum matches and is unit-norm; the manifest ids equal the current
    chunk ids (no orphans, none missing); content hashes match the current source text.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .identity import make_records
from .store import DimensionMismatch, ManifestError


@dataclass(frozen=True)
class SearchHit:
    id: str
    score: float
    path: str
    kind: str


def search(index, query_vec, k: int = 10) -> list[SearchHit]:
    q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
    if q.shape[0] != index.embedder.dims:
        raise DimensionMismatch(f"query has {q.shape[0]} dims, index has {index.embedder.dims}")
    n = np.linalg.norm(q)
    q = q / n if n else q
    ids, mat = index.live()
    if not ids:
        return []
    scores = mat @ q
    order = np.lexsort((np.arange(len(ids)), -np.round(scores, 6)))[:k]  # ids are sorted
    meta = {c["id"]: c for c in index.manifest()["chunks"]}
    return [
        SearchHit(ids[i], float(scores[i]), meta[ids[i]]["path"], meta[ids[i]]["kind"])
        for i in order
    ]


def verify(index, chunks, graph=None) -> list[str]:
    problems: list[str] = []
    st = index.store
    try:
        act = st.read_active()
    except (ManifestError, DimensionMismatch) as exc:
        return [f"pointer: {exc}"]
    if act is None:
        return ["pointer: no ACTIVE manifest"]
    m = act[1]
    ids = [c["id"] for c in m["chunks"]]
    for i in sorted({x for x in ids if ids.count(x) > 1}):
        problems.append(f"duplicate id in manifest: {i}")
    corrupt = set(st.corrupt_keys())
    for c in m["chunks"]:
        k = c["embed_key"]
        if k not in st.keys():
            problems.append(f"missing vector: {c['id']}")
        elif k in corrupt:
            problems.append(f"corrupt vector (checksum/shape/finite): {c['id']}")
        elif abs(float(np.linalg.norm(st.get(k))) - 1.0) > 1e-3:
            problems.append(f"vector not unit-norm: {c['id']}")

    class _G:  # edge digests are not source-derived; only hash the text here
        nx = None

        def __contains__(self, _n):
            return False

    cur = make_records(chunks, graph if graph is not None else _G())
    have = {c["id"]: c for c in m["chunks"]}
    for i in sorted(set(have) - set(cur)):
        problems.append(f"orphan manifest id (not in source): {i}")
    for i in sorted(set(cur) - set(have)):
        problems.append(f"chunk missing from index: {i}")
    for i in sorted(set(cur) & set(have)):
        if cur[i].content_hash != have[i]["content_hash"]:
            problems.append(f"content hash mismatch (source changed): {i}")
    return problems
