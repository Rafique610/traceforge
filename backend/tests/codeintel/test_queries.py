from traceforge.codeintel import (
    GraphConfig,
    build_graph,
    changed_symbols,
    distance,
    impact,
    impact_set,
    neighbors,
    signature_changes,
    symbol_at,
    weighted_distances,
)

RUN = "func:svc/app.py::run"
SAVE = "func:svc/store.py::Store.save"
PING, PONG = "func:svc/ping_pong.py::ping", "func:svc/pong_mod.py::pong"


def test_distance(graph):
    assert distance(graph, RUN, RUN) == 0
    assert distance(graph, RUN, "func:svc/app.py::handle") == 1
    assert distance(graph, RUN, "cfg:REDIS_HOST") == 1  # config binding is one hop
    assert distance(graph, "func:svc/store.py::connect", "func:svc/settings.py::get_cfg") == 2
    ping, inject = "func:svc/app.py::ping", "func:svc/app.py::inject"
    assert distance(graph, ping, inject) is None  # unknown: nodes are ignored
    assert distance(graph, RUN, "unknown:callback") is None
    assert distance(graph, RUN, "nope") is None
    assert distance(graph, RUN, PING) is None  # unreachable
    assert distance(graph, ping, inject, edge_types=()) == 2  # structural edges only when asked
    assert distance(graph, "svc:api", "file:svc/__main__.py") == 1  # service_runs


def test_neighbors(graph):
    n = dict(neighbors(graph, RUN, 1))
    assert n["func:svc/app.py::handle"] == 1 and "cfg:REDIS_HOST" in n
    assert all(h == 1 for h in n.values())
    assert max(dict(neighbors(graph, RUN, 5)).values()) == 2  # capped at 2 hops
    got = neighbors(graph, RUN, 2)
    assert got == sorted(got, key=lambda x: (x[1], x[0]))
    assert neighbors(graph, "missing") == []


def test_cycles_terminate(graph):
    assert distance(graph, PING, PONG) == 1
    assert PONG in impact(graph, PING) and PING in impact(graph, PONG)


def test_impact_set_reverse_edges(graph):
    r = impact_set(graph, [SAVE], signature_changed={SAVE})
    by = {e.node: e for e in r.entries}
    assert by["func:svc/store.py::SubStore.again"].via == "called_by"
    assert by["func:svc/app.py::handle"].breaking is True
    assert by[RUN].depth == 2 and by[RUN].breaking is False  # transitive caller
    assert "test:svc/tests/test_app.py::test_store_save" in r.tests
    assert "func:svc/store.py::connect" in impact(graph, "cfg:EXTRA_KEY")  # config reader
    assert impact_set(graph, ["unknown:x"]).entries == []
    assert all(e.depth <= 3 for e in r.entries)


def test_symbol_at(graph):
    n = graph.node(SAVE)
    assert symbol_at(graph, "svc/store.py", n["start"] + 1) == SAVE
    assert symbol_at(graph, "svc\\store.py", n["start"]) == SAVE
    abs_path = (graph.repo / "svc" / "store.py").as_posix()
    assert symbol_at(graph, abs_path, graph.node("func:svc/store.py::helper")["start"])
    assert symbol_at(graph, "svc/store.py", 1) is None
    assert symbol_at(graph, "other.py", 3) is None


def test_hub_data_and_weights(graph):
    d = graph.node("cfg:REDIS_HOST")
    assert d["degree"] >= 2 and d["hub_factor"] == 1.0
    assert graph.config.edge_weights["reads_config"] > graph.config.edge_weights["calls"]
    wd = weighted_distances(graph, RUN, 10)
    assert wd["cfg:REDIS_HOST"] < wd[SAVE]  # config binding closer than a call chain
    g = build_graph(graph.repo, "x", cache_dir=None, config=GraphConfig(hub_degree_threshold=1))
    assert g.node(RUN)["hub_factor"] < 1.0


def test_signature_changes(repo):
    old = build_graph(repo, "a", cache_dir=None)
    f = repo / "svc" / "store.py"
    f.write_text(
        f.read_text().replace("def save(self, item=None) -> bool", "def save(self, item, force)")
    )
    new = build_graph(repo, "b", cache_dir=None)
    sc = signature_changes(old, new)
    assert list(sc) == [SAVE]
    assert changed_symbols(old, new) == [SAVE]
    r = impact_set(new, changed_symbols(old, new), signature_changed=set(sc))
    assert any(e.breaking for e in r.entries)
