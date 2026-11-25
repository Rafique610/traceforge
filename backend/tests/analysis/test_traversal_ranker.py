# ruff: noqa: E501
import dataclasses

import pytest

from traceforge.analysis import (
    RankerConfig,
    RuntimeFacts,
    TraversalConfig,
    build_overlay,
    config_affecting,
    depended_on_by,
    depends_on,
    rank_root_causes,
    seeds_from_retrieval,
    seeds_from_runtime,
    traverse,
    what_else_could_change,
)
from traceforge.analysis import priors as P
from traceforge.analysis import traversal as T
from traceforge.analysis.ranker import Seed
from traceforge.codeintel import build_graph

RUN = "func:core.py::Base.run"


def sig(rs):
    return [(r.node, r.depth, round(r.weight, 9), r.evidence) for r in rs]


def test_traversal_is_deterministic_and_explained(graph):
    og = build_overlay(graph)
    a = traverse(og, [RUN], "reverse")
    b = traverse(og, [RUN], "reverse")
    assert sig(a) == sig(b) and a
    for r in a:
        assert r.steps and r.steps[-1].dst == r.node
        assert all(
            s.provenance and s.type and s.evidence for s in r.steps
        )  # file:line, type, class


def test_per_direction_depth(graph):
    og = build_overlay(graph)
    d1 = traverse(og, ["func:api.py::addr"], "forward", TraversalConfig().with_depth(forward=1))
    d3 = traverse(og, ["func:api.py::addr"], "forward", TraversalConfig().with_depth(forward=3))
    assert max(r.depth for r in d1) == 1
    assert {r.node for r in d1} <= {r.node for r in d3}
    assert not traverse(og, [RUN], "reverse", TraversalConfig().with_depth(reverse=0))


def test_node_cap_top_n_and_edge_budget(graph):
    og = build_overlay(graph)
    full = traverse(og, [RUN], "reverse", TraversalConfig().with_depth(reverse=3))
    capped = traverse(
        og,
        [RUN],
        "reverse",
        dataclasses.replace(TraversalConfig().with_depth(reverse=3), node_cap=2),
    )
    assert len(capped) == 2 and len(full) > 2
    topn = traverse(og, [RUN], "reverse", dataclasses.replace(TraversalConfig(), top_n=1))
    assert sum(1 for r in topn if r.depth == 1) == 1
    budget = traverse(og, [RUN], "reverse", dataclasses.replace(TraversalConfig(), edge_budget=1))
    from collections import Counter

    assert max(Counter(r.steps[-1].type for r in budget).values()) == 1


def test_cycles_are_safe(tmp_path):
    (tmp_path / "a.py").write_text("import b\n\n\ndef f():\n    return b.g()\n")
    (tmp_path / "b.py").write_text("import a\n\n\ndef g():\n    return a.f()\n")
    og = build_overlay(build_graph(tmp_path, "c", cache_dir=None))
    rs = traverse(og, ["func:a.py::f"], "forward", TraversalConfig().with_depth(forward=6))
    nodes = [r.node for r in rs]
    assert len(nodes) == len(set(nodes)) and "func:b.py::g" in nodes


def test_hub_is_reported_but_not_expanded_unless_named(tmp_path):
    (tmp_path / "hub.py").write_text(
        "def norm(x):\n    return deep(x)\n\n\ndef deep(x):\n    return x\n"
    )
    callers = "".join(f"\ndef c{i}(x):\n    return norm(x)\n\n" for i in range(15))
    (tmp_path / "callers.py").write_text(
        "from hub import norm\n" + callers + "\ndef entry(x):\n    return norm(x)\n"
    )
    og = build_overlay(build_graph(tmp_path, "h", cache_dir=None))
    norm = "func:hub.py::norm"
    assert og.node(norm)["degree_all"] > P.HUB_STOP_DEGREE
    plain = traverse(og, ["func:callers.py::entry"], "forward", TraversalConfig())
    assert norm in {r.node for r in plain} and "func:hub.py::deep" not in {r.node for r in plain}
    assert next(r for r in plain if r.node == norm).hub
    named = traverse(
        og, ["func:callers.py::entry"], "forward", TraversalConfig(named=frozenset({norm}))
    )
    assert "func:hub.py::deep" in {r.node for r in named}


def test_direct_vs_inferred_distinction(graph):
    og = build_overlay(graph)
    a = depended_on_by(og, "func:core.py::Base.run")
    assert any(r.node == "func:svc.py::go" and r.kind == "inferred" for r in a.all)  # name-resolved
    assert any(r.kind == "direct" and r.direct for r in a.all) or any(
        r.node.endswith("Child.run") for r in a.all
    )
    for r in a.inferred:
        assert not r.direct and r.evidence in ("inferred", "unknown")


def test_five_questions(graph):
    og = build_overlay(graph)
    dep = depends_on(og, "func:api.py::addr")
    assert {r.node for r in dep.all} >= {"func:util.py::norm", "cfg:HOST"}
    rev = depended_on_by(og, "func:util.py::norm")
    assert "func:api.py::addr" in {r.node for r in rev.direct}
    cfg = config_affecting(og, "func:api.py::addr")
    nodes = {r.node for r in cfg.all}
    assert "cfg:HOST" in nodes and "svc:web" in nodes
    assert "values are not stored" in cfg.note
    t = T.tests_exercising(og, "func:util.py::norm")
    assert "test:tests/test_api.py::test_addr" in {r.node for r in t.all}  # via its caller addr
    sub = what_else_could_change(og, "class:core.py::Base")
    assert {"class:core.py::Child", "class:svc.py::Mixin"} <= {r.node for r in sub.all}
    over = what_else_could_change(og, RUN)
    assert "func:core.py::Child.run" in {r.node for r in over.all}
    assert depends_on(og, "func:svc.py::dyn").unknown_sites  # not analysable, listed


def test_unknown_node_is_leaf_and_never_direct(graph):
    og = build_overlay(graph)
    a = depends_on(og, "func:svc.py::dyn")
    for r in a.all:
        if r.node.startswith("unknown:"):
            assert r.kind == "inferred" and not r.direct


# ------------------------------------------------------------------ ranker
def runtime(failing="tests/test_api.py::test_addr", frames=(("api.py", 6),), text=""):
    return failing, list(frames), text


def test_ranker_deterministic_with_reason_chains(graph):
    failing, frames, text = runtime()
    og = build_overlay(graph, RuntimeFacts(frames=frames, failing_tests=[failing]))
    seeds = seeds_from_runtime(og, frames, [failing], "address looks wrong")
    r1 = rank_root_causes(og, seeds)
    r2 = rank_root_causes(og, seeds)
    assert r1.ids() == r2.ids() and r1.candidates
    top = {c.node: c for c in r1.candidates}
    assert "func:api.py::addr" in top and "cfg:HOST" in top and "func:util.py::norm" in top
    c = top["cfg:HOST"]
    assert (
        c.reasons[0].startswith("seed ")
        and c.steps
        and c.evidence in ("static", "inferred", "observed")
    )
    assert all(s.provenance for s in c.steps)
    assert [x.rank for x in r1.candidates] == list(range(1, len(r1.candidates) + 1))
    assert all(x.score >= y.score for x, y in zip(r1.candidates, r1.candidates[1:], strict=False))


def test_ranker_never_takes_gold_and_excludes_tests_files(graph):
    import inspect

    from traceforge.analysis import ranker

    params = inspect.signature(ranker.rank_root_causes).parameters
    assert set(params) == {"og", "seeds", "cfg"}  # no gold / hidden / expected parameter
    og = build_overlay(graph)
    seeds = seeds_from_runtime(og, [], ["tests/test_api.py::test_addr"], "")
    r = rank_root_causes(og, seeds)
    assert all(not c.node.startswith(("test:", "file:", "unknown:")) for c in r.candidates)


def test_seed_sources_and_symptom_name_collision(graph):
    og = build_overlay(graph)
    seeds = seeds_from_runtime(og, [("core.py", 3)], [], "Traceback in helper and run")
    kinds = {(s.kind, s.node) for s in seeds}
    assert ("frame", "func:core.py::Base.run") in kinds
    sym = [
        s
        for s in seeds
        if s.kind == "symptom"
        and s.node.endswith("::run")
        or s.kind == "symptom"
        and s.node.endswith(".run")
    ]
    assert sym and all(
        s.relevance < P.SEED_PRIOR["symptom"] for s in sym
    )  # `run` names several nodes
    ret = seeds_from_retrieval(og, [("func:util.py::norm", 0.5), ("func:missing::x", 1.0)])
    assert [s.node for s in ret] == ["func:util.py::norm"] and ret[0].kind == "retrieval"


def test_abstains_on_unresolved_dynamic_call(graph):
    og = build_overlay(graph)
    r = rank_root_causes(og, [Seed("func:svc.py::dyn", "frame", 1.0, True, "frame")])
    assert r.abstain and any("dynamic" in u for u in r.unresolved)
    ok = rank_root_causes(og, [Seed("func:api.py::addr", "frame", 1.0, True, "frame")])
    assert not ok.abstain
    # a name-resolved call site (go -> obj.run) is inferred, not blind: no abstention
    assert not rank_root_causes(og, [Seed("func:svc.py::go", "frame", 1.0, True, "frame")]).abstain


def test_undeclared_key_is_boosted(graph):
    og = build_overlay(graph)
    seeds = [Seed("func:api.py::port", "frame", 1.0, True, "f")]
    boosted = rank_root_causes(og, seeds)
    plain = rank_root_causes(og, seeds, RankerConfig(undeclared_boost=1.0))
    s = lambda r: {c.node: c.score for c in r.candidates}["cfg:PORT"]  # noqa: E731
    assert s(boosted) > s(plain)  # PORT is read but set by no compose service


def test_forward_causes_rank_above_reverse_dependants(graph):
    og = build_overlay(graph)
    r = rank_root_causes(og, [Seed("func:api.py::addr", "frame", 1.0, True, "f")])
    ids = r.ids()
    assert ids.index("func:util.py::norm") < len(ids)
    assert "func:api.py::port" not in ids[:1]


@pytest.mark.parametrize("budget", [1, 3])
def test_top_k_respected(graph, budget):
    og = build_overlay(graph)
    r = rank_root_causes(
        og, [Seed("func:api.py::addr", "frame", 1.0, True, "f")], RankerConfig(top_k=budget)
    )
    assert len(r.candidates) == budget
