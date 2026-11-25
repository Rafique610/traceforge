# ruff: noqa: E501
import copy

from traceforge.analysis.overlay import RuntimeFacts, build_overlay, path_evidence


def edge_types(og, src):
    return {(e.type, e.dst, e.evidence) for e in og.edges_from(src)}


def test_original_graph_is_never_mutated(graph):
    before_nodes = copy.deepcopy(dict(graph.nx.nodes(data=True)))
    before_edges = sorted(
        (u, v, k, tuple(sorted(d.items()))) for u, v, k, d in graph.nx.edges(keys=True, data=True)
    )
    og = build_overlay(
        graph,
        RuntimeFacts(frames=[("core.py", 3)], failing_tests=["tests/test_core.py::test_base"]),
    )
    after_edges = sorted(
        (u, v, k, tuple(sorted(d.items()))) for u, v, k, d in graph.nx.edges(keys=True, data=True)
    )
    assert before_edges == after_edges
    assert dict(graph.nx.nodes(data=True)) == before_nodes
    assert og.nx is not graph.nx and og.base is graph
    assert all("evidence" not in d for _u, _v, d in graph.nx.edges(data=True))
    assert all("evidence" in d for _u, _v, d in og.nx.edges(data=True))
    assert og.nx.number_of_edges() > graph.nx.number_of_edges()


def test_inheritance_same_file_import_hop_and_module_attribute(graph):
    og = build_overlay(graph)
    child, base = "class:core.py::Child", "class:core.py::Base"
    assert ("inherits", base, "static") in edge_types(og, child)
    assert ("subclassed_by", child, "static") in edge_types(og, base)
    # one import hop: `from core import Child` in svc.py ; module attr form: core.Base
    assert ("inherits", child, "static") in edge_types(og, "class:svc.py::GrandChild")
    assert ("inherits", base, "static") in edge_types(og, "class:svc.py::Mixin")


def test_external_base_is_unknown_and_builtins_are_not(graph):
    og = build_overlay(graph)
    ext = edge_types(og, "class:svc.py::Ext")
    assert any(
        t == "inherits" and d.startswith("unknown:base:") and ev == "unknown" for t, d, ev in ext
    )
    assert og.kind("unknown:base:Remote") == "unknown"


def test_overrides_edges_and_reverse(graph):
    og = build_overlay(graph)
    assert ("overrides", "func:core.py::Base.run", "static") in edge_types(
        og, "func:core.py::Child.run"
    )
    assert ("overridden_by", "func:core.py::Child.run", "static") in edge_types(
        og, "func:core.py::Base.run"
    )
    # nearest ancestor with the method: GrandChild.helper overrides Base.helper through Child
    assert ("overrides", "func:core.py::Base.helper", "static") in edge_types(
        og, "func:svc.py::GrandChild.helper"
    )
    assert og.stats["overrides"] == 2


def test_name_resolution_is_inferred_never_static(graph):
    og = build_overlay(graph)
    go = edge_types(og, "func:svc.py::go")
    assert any(
        t == "calls" and d == "func:core.py::Base.run" and ev == "inferred" for t, d, ev in go
    )
    assert any(t == "calls" and d.startswith("unknown:") and ev == "unknown" for t, d, ev in go)
    assert not any(t == "calls" and d.startswith("func:") and ev == "static" for t, d, ev in go)


def test_dynamic_dispatch_marker_is_unknown(graph):
    og = build_overlay(graph)
    dyn = edge_types(og, "func:svc.py::dyn")
    assert any(d.startswith("unknown:dynamic:getattr") and ev == "unknown" for _t, d, ev in dyn)


def test_evidence_mapping_from_confidence_and_unknown_nodes(graph):
    og = build_overlay(graph)
    plain = edge_types(og, "func:svc.py::plain")
    assert ("calls", "func:core.py::Base.run", "inferred") in plain  # Base().run(v): name-resolved
    assert ("calls", "class:core.py::Base", "static") in plain  # Base() constructor call
    assert path_evidence([]) == "static"
    assert path_evidence(["static", "inferred"]) == "inferred"
    assert path_evidence(["static", "unknown", "inferred"]) == "unknown"
    assert path_evidence(["observed", "observed"]) == "observed"
    assert path_evidence(["observed", "static"]) == "static"
    for _u, _v, d in og.nx.edges(data=True):
        assert d["evidence"] in ("static", "inferred", "unknown")  # no runtime facts => no observed


def test_observed_only_from_supplied_runtime_facts(graph):
    none = build_overlay(graph)
    assert not none.observed
    assert all(d["evidence"] != "observed" for _u, _v, d in none.nx.edges(data=True))
    facts = RuntimeFacts(
        frames=[("core.py", 3), ("core.py", 6)],  # Base.run -> Base.helper, adjacent frames
        failing_tests=["tests/test_core.py::test_base"],
    )
    og = build_overlay(graph, facts)
    assert set(og.observed) >= {
        "func:core.py::Base.run",
        "func:core.py::Base.helper",
        "test:tests/test_core.py::test_base",
    }
    run_to_helper = [
        e
        for e in og.edges_from("func:core.py::Base.run", ("calls",))
        if e.dst == "func:core.py::Base.helper"
    ]
    assert run_to_helper and run_to_helper[0].evidence == "observed"
    # an edge between a non-observed node stays static
    assert all(e.evidence != "observed" for e in og.edges_from("func:api.py::addr"))
    # unresolved frames create nothing
    og2 = build_overlay(graph, RuntimeFacts(frames=[("nope.py", 1)]))
    assert not og2.observed


def test_hidden_paths_are_removed_from_the_copy(graph):
    og = build_overlay(graph, hidden_paths=["tests_hidden"])
    assert not any(
        (d.get("path") or "").startswith("tests_hidden") for _n, d in og.nx.nodes(data=True)
    )
    assert any(
        (d.get("path") or "").startswith("tests_hidden") for _n, d in graph.nx.nodes(data=True)
    )
