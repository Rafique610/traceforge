# ruff: noqa: E501
"""P5-S07 tests: FakeEmbedder only (plus one optional real-Ollama test)."""

import json
import os
import textwrap
import urllib.request

import numpy as np
import pytest

from traceforge.codeintel import build_graph
from traceforge.index import (
    DimensionMismatch,
    EmbeddingIndex,
    FakeEmbedder,
    OllamaEmbedder,
    embed_key,
    verify,
)
from traceforge.index import store as store_mod
from traceforge.retrieval.corpus import build_corpus

A = """
def alpha(x):
    return x + 1

def beta(x):
    return alpha(x) * 2

def gamma(x):
    return x - 1
"""
B = """
from a import alpha

def delta(x):
    return alpha(x)
"""


def write(repo, files):
    for rel, src in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if src is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(textwrap.dedent(src).lstrip(), "utf-8")


def snapshot(repo):
    g = build_graph(repo, "sha", cache_dir=None)
    return build_corpus(g).chunks, g


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    write(r, {"a.py": A, "b.py": B})
    return r


def names(texts):
    return sorted(t.split("\n")[0].split(" ", 1)[1] for t in texts)


def make(tmp_path, **kw):
    emb = FakeEmbedder(**kw)
    return EmbeddingIndex(tmp_path / "ns", emb), emb


def first_sync(repo, tmp_path):
    idx, emb = make(tmp_path)
    chunks, g = snapshot(repo)
    rep = idx.sync(chunks, g, "c1")
    assert rep.new == len(chunks) and rep.texts_embedded == len(chunks)
    assert verify(idx, chunks) == []
    emb.calls.clear()
    return idx, emb, len(chunks)


def resync(idx, repo, commit):
    chunks, g = snapshot(repo)
    return idx.sync(chunks, g, commit), chunks


def test_unchanged_resync_embeds_nothing(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    rep, _ = resync(idx, repo, "c2")
    assert emb.calls == [] and rep.unchanged == n and rep.reused == n and rep.embed_calls == 0


def test_s1_function_body_changes(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    write(repo, {"a.py": A.replace("x + 1", "x + 100")})
    rep, chunks = resync(idx, repo, "c2")
    assert names(emb.texts) == ["alpha"]
    assert (rep.modified, rep.new, rep.deleted, rep.texts_embedded, rep.reused) == (
        1,
        0,
        0,
        1,
        n - 1,
    )
    assert verify(idx, chunks) == []


def test_s2_function_added(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    write(repo, {"a.py": A + "\ndef omega(x):\n    return 7\n"})
    rep, chunks = resync(idx, repo, "c2")
    assert names(emb.texts) == ["omega"]
    assert (rep.new, rep.modified, rep.reused) == (1, 0, n)
    assert len(idx.live()[0]) == n + 1 and verify(idx, chunks) == []


def test_s3_function_deleted(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    write(repo, {"a.py": A.replace("def gamma(x):\n    return x - 1\n", "")})
    rep, chunks = resync(idx, repo, "c2")
    assert emb.calls == [] and rep.deleted == 1 and rep.reused == n - 1
    assert "sym:a.py::gamma" not in idx.live()[0]
    assert verify(idx, chunks) == []
    cached = len(idx.store.keys())
    assert cached == n  # cache entry kept until gc
    assert idx.gc("active") == 1 and len(idx.store.keys()) == n - 1


def test_s4_rename_reembeds_but_move_reuses(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    # rename: the qualname/def line is part of the embedded text -> honest 1 re-embed
    write(repo, {"a.py": A.replace("gamma", "gamma2")})
    rep, _ = resync(idx, repo, "c2")
    assert names(emb.texts) == ["gamma2"] and rep.new == 1 and rep.deleted == 1
    # move of a whole file: same qualnames and bodies, new path -> MOVED, zero embeds
    emb.calls.clear()
    write(repo, {"a.py": None, "pkg/a.py": A.replace("gamma", "gamma2")})
    rep, chunks = resync(idx, repo, "c3")
    assert emb.calls == [] and rep.moved >= 3 and rep.new == 0 and rep.deleted == 0
    assert rep.reused == len(chunks) and verify(idx, chunks) == []
    assert idx.manifest()["chunks"][0]["path"] in ("pkg/a.py", "b.py")


def test_s5_import_change_updates_edges_only(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    before = {c["id"]: c["edge_digest"] for c in idx.manifest()["chunks"]}
    gd = idx.manifest()["graph_digest"]
    # delta calls a different function through the import; delta's own text is unchanged
    write(repo, {"b.py": B.replace("from a import alpha", "from a import beta as alpha")})
    rep, chunks = resync(idx, repo, "c2")
    assert emb.calls == []
    assert rep.edge_only_updates >= 1 and rep.reused == n
    after = {c["id"]: c["edge_digest"] for c in idx.manifest()["chunks"]}
    assert after != before and idx.manifest()["graph_digest"] != gd
    assert verify(idx, chunks) == []


def test_s6_model_upgrade_new_namespace(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    ids, mat = idx.live()
    emb2 = FakeEmbedder(revision="2", dims=24)
    idx2 = EmbeddingIndex(tmp_path / "ns", emb2)
    chunks, g = snapshot(repo)
    rep = idx2.sync(chunks, g, "c1")
    assert rep.texts_embedded == n and rep.reused == 0 and len(emb2.texts) == n
    assert idx2.store.dir != idx.store.dir
    # old namespace is intact and still queryable
    old = EmbeddingIndex(tmp_path / "ns", FakeEmbedder())
    assert verify(old, chunks) == [] and old.live()[0] == ids
    assert np.array_equal(old.live()[1], mat)
    q = FakeEmbedder().embed([old_text(chunks[0])])[0]
    assert old.search(q, 1)[0].id == chunks[0].hit_id
    assert verify(idx2, chunks) == []


def old_text(c):
    from traceforge.index.identity import embedding_text

    return embedding_text(c)


def test_crash_between_temp_and_pointer_swap(repo, tmp_path, monkeypatch):
    idx, emb, n = first_sync(repo, tmp_path)
    before = idx.manifest()
    write(repo, {"a.py": A.replace("x + 1", "x + 5")})
    real = os.replace

    def boom(src, dst):
        if str(dst).endswith("ACTIVE.json"):
            raise OSError("simulated crash")
        return real(src, dst)

    monkeypatch.setattr(store_mod.os, "replace", boom)
    chunks, g = snapshot(repo)
    with pytest.raises(OSError):
        idx.sync(chunks, g, "c2")
    monkeypatch.undo()
    fresh = EmbeddingIndex(tmp_path / "ns", FakeEmbedder())
    old_chunks, _ = snapshot_old(repo, tmp_path)
    assert fresh.manifest() == before
    assert verify(fresh, old_chunks) == []
    # resume: the vector already persisted, so no new embed call is needed
    emb2 = FakeEmbedder()
    idx3 = EmbeddingIndex(tmp_path / "ns", emb2)
    rep = idx3.sync(chunks, g, "c2")
    assert rep.texts_embedded == 0 and verify(idx3, chunks) == []


def snapshot_old(repo, tmp_path):
    other = tmp_path / "orig"
    write(other, {"a.py": A, "b.py": B})
    return snapshot(other)


def test_crash_mid_batches_resumes_without_duplicates(repo, tmp_path):
    chunks, g = snapshot(repo)

    class Flaky(FakeEmbedder):
        def embed(self, texts):
            if len(self.calls) == 1:
                raise RuntimeError("die on 2nd batch")
            return super().embed(texts)

    emb = Flaky()
    idx = EmbeddingIndex(tmp_path / "ns", emb, batch_size=3)
    with pytest.raises(RuntimeError):
        idx.sync(chunks, g, "c1")
    assert idx.store.read_active() is None and len(idx.store.keys()) == 3
    emb2 = FakeEmbedder()
    idx2 = EmbeddingIndex(tmp_path / "ns", emb2, batch_size=3)
    rep = idx2.sync(chunks, g, "c1")
    assert rep.texts_embedded == len(chunks) - 3 and verify(idx2, chunks) == []


def test_dims_mismatch_refused(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    with pytest.raises(DimensionMismatch):
        idx.store.put_many(["k"], np.ones((1, 7), np.float32))
    with pytest.raises(DimensionMismatch):
        idx.search(np.ones(7), 3)

    class Liar(FakeEmbedder):
        def embed(self, texts):
            return np.ones((len(texts), 5), np.float32)

    chunks, g = snapshot(repo)
    with pytest.raises(DimensionMismatch):
        EmbeddingIndex(tmp_path / "other", Liar()).sync(chunks, g, "c1")
    # a namespace dir cannot be reopened with other dims
    meta = idx.store.dir / "model.json"
    d = json.loads(meta.read_text())
    d["dims"] = 99
    meta.write_text(json.dumps(d))
    with pytest.raises(DimensionMismatch):
        EmbeddingIndex(tmp_path / "ns", FakeEmbedder())


def test_verifier_catches_corruption_and_source_drift(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    chunks, _ = snapshot(repo)
    # corrupt one vector in its shard while keeping its checksum
    shard = sorted((idx.store.dir / "shards").glob("*.npz"))[0]
    with np.load(shard) as z:
        keys, vecs, sums = z["keys"], z["vecs"].copy(), z["sums"]
    vecs[0, 0] += 0.5
    np.savez(shard, keys=keys, vecs=vecs, sums=sums)
    fresh = EmbeddingIndex(tmp_path / "ns", FakeEmbedder())
    probs = verify(fresh, chunks)
    assert len(probs) == 1 and probs[0].startswith("corrupt vector")
    # source drift: hash mismatch
    write(repo, {"a.py": A.replace("x - 1", "x - 9")})
    chunks2, _ = snapshot(repo)
    assert any(
        p.startswith("content hash mismatch") and "gamma" in p for p in verify(fresh, chunks2)
    )
    # a corrupt cached vector is not trusted: the next sync re-embeds it
    rep = fresh.sync(chunks2, snapshot(repo)[1], "c2")
    assert rep.texts_embedded == 2 and verify(fresh, chunks2) == []


def test_verifier_catches_dangling_pointer_and_orphans(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    chunks, _ = snapshot(repo)
    assert any("orphan" in p for p in verify(idx, chunks[:-1]))
    ptr = idx.store.dir / "ACTIVE.json"
    d = json.loads(ptr.read_text())
    d["sha256"] = "0" * 64
    ptr.write_text(json.dumps(d))
    assert verify(idx, chunks)[0].startswith("pointer")


def test_search_deterministic_tie_break(tmp_path):
    from traceforge.index.search import search

    idx, emb = make(tmp_path)

    class C:
        def __init__(self, i, text):
            self.hit_id, self.node_id, self.kind, self.path = i, i, "symbol", "x.py"
            self.start = self.end = 1
            self.name, self.lines, self.notes, self.parent = i, [(1, text)], [], None

    import networkx

    empty = networkx.MultiDiGraph()

    class G:
        nx = empty

        def __contains__(self, _n):
            return False

    chunks = [C(f"sym:x.py::{n}", "same body") for n in ("c", "a", "b")]
    chunks[0].name = chunks[1].name = chunks[2].name = "same"  # identical embedding text
    idx.sync(chunks, G(), "c1")
    q = emb.embed(["symbol same\nsame body"])[0]
    r1, r2 = search(idx, q, 3), search(idx, q, 3)
    assert [h.id for h in r1] == ["sym:x.py::a", "sym:x.py::b", "sym:x.py::c"] == [h.id for h in r2]
    assert r1[0].score == pytest.approx(1.0, abs=1e-5)


def test_search_ranks_exact_text_first(repo, tmp_path):
    idx, emb, n = first_sync(repo, tmp_path)
    chunks, _ = snapshot(repo)
    for c in chunks:
        hit = idx.search(emb.embed([old_text(c)])[0], 1)[0]
        assert hit.id == c.hit_id


def test_embed_key_depends_on_every_component():
    base = FakeEmbedder()
    k = embed_key("h", base)
    assert k != embed_key("h2", base)
    assert k != embed_key("h", FakeEmbedder(model_id="m"))
    assert k != embed_key("h", FakeEmbedder(revision="9"))
    assert k != embed_key("h", FakeEmbedder(dims=8))
    assert k != embed_key("h", FakeEmbedder(preprocessing_version="p2"))


def test_two_builds_identical(repo, tmp_path):
    chunks, g = snapshot(repo)
    a = EmbeddingIndex(tmp_path / "n1", FakeEmbedder())
    b = EmbeddingIndex(tmp_path / "n2", FakeEmbedder())
    a.sync(chunks, g, "c1")
    b.sync(chunks, g, "c1")
    assert a.manifest() == b.manifest() and np.array_equal(a.live()[1], b.live()[1])


def _ollama_up():
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
            return b"all-minilm:22m" in r.read()
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="local Ollama all-minilm:22m not available")
def test_real_ollama_all_minilm(repo, tmp_path):
    emb = OllamaEmbedder("all-minilm:22m")
    assert emb.dims == 384
    idx = EmbeddingIndex(tmp_path / "ns", emb)
    chunks, g = snapshot(repo)
    rep = idx.sync(chunks, g, "c1")
    assert rep.texts_embedded == len(chunks) and verify(idx, chunks) == []
    assert idx.search(emb.embed([old_text(chunks[0])])[0], 1)[0].id == chunks[0].hit_id
