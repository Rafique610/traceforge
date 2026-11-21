from traceforge.codeintel import build_graph
from traceforge.retrieval.corpus import get_corpus
from traceforge.retrieval.lexical import index_for, tokenize


def test_tokenizer_splits_identifiers_and_keeps_whole_name():
    assert tokenize("redis_host") == ["redis", "host", "redis_host"]
    assert tokenize("OrderQueue.getHTTPClient") == [
        "order", "queue", "orderqueue", "get", "http", "client", "gethttpclient",
    ]  # fmt: skip
    assert tokenize("self x") == []  # stop words and single characters dropped


def test_bm25_ranking_on_fixed_corpus_is_deterministic(tiny_repo):
    g = build_graph(tiny_repo, "t", cache_dir=None)
    idx = index_for(get_corpus(g))
    q = tokenize("charge the card failed")
    first = idx.candidates(q, 50)
    assert [c.hit_id for c, _ in first][0] == "sym:app/orders.py::charge_card"
    assert idx.candidates(q, 50) == first
    # a freshly built index over a rebuilt graph gives the identical ranking and scores
    again = index_for(get_corpus(build_graph(tiny_repo, "t", cache_dir=None))).candidates(q, 50)
    assert [(c.hit_id, s) for c, s in again] == [(c.hit_id, s) for c, s in first]
    assert max(s for _, s in first) == 1.0


def test_no_query_terms_no_candidates(tiny_repo):
    g = build_graph(tiny_repo, "t", cache_dir=None)
    assert index_for(get_corpus(g)).candidates([], 50) == []
