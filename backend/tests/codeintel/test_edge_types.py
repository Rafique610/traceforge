"""One asserted instance per edge type on the purpose-built fixture repo."""

import pytest
from conftest import edges, has_edge

from traceforge.codeintel import build_graph
from traceforge.codeintel.config import FORWARD_TYPES, REVERSE_OF, SOURCES

RUN, HANDLE = "func:svc/app.py::run", "func:svc/app.py::handle"
SAVE = "func:svc/store.py::Store.save"


def test_calls_resolved_across_modules_and_classes(graph):
    assert has_edge(graph, "calls", RUN, "func:svc/settings.py::get_cfg")  # from-import
    assert has_edge(graph, "calls", RUN, "func:svc/store.py::connect")
    assert has_edge(graph, "calls", RUN, HANDLE)  # same module
    assert has_edge(graph, "calls", HANDLE, "func:svc/store.py::helper")  # module.attr
    assert has_edge(graph, "calls", HANDLE, SAVE)  # typed local variable
    assert has_edge(graph, "calls", SAVE, "func:svc/store.py::Store._flush")  # self.method
    again = "func:svc/store.py::SubStore.again"
    assert has_edge(graph, "calls", again, SAVE)  # inherited through a resolved base
    assert has_edge(graph, "calls", "file:svc/__main__.py", RUN)  # module-level call


@pytest.mark.parametrize("caller", ["dispatch", "plugin", "inject", "ping"])
def test_dynamic_calls_are_unknown_never_guessed(graph, caller):
    out = [e for e in edges(graph, "calls") if e[0] == f"func:svc/app.py::{caller}"]
    assert len(out) == 1
    _u, v, d = out[0]
    assert v.startswith("unknown:") and graph.node(v)["kind"] == "unknown"
    assert d["confidence"] == 0.2 and d["unknown"] is True


def test_imports_and_defined_in(graph):
    assert has_edge(graph, "imports", "file:svc/app.py", "file:svc/store.py")
    assert has_edge(graph, "imports", "file:svc/app.py", "file:svc/settings.py")  # relative
    assert has_edge(graph, "defined_in", SAVE, "class:svc/store.py::Store")
    assert has_edge(graph, "defined_in", "class:svc/store.py::Store", "file:svc/store.py")
    assert has_edge(graph, "defined_in", "cfg:REDIS_HOST", "file:compose.yaml")


def test_circular_imports_and_calls_are_fine(graph):
    assert has_edge(graph, "imports", "file:svc/ping_pong.py", "file:svc/pong_mod.py")
    assert has_edge(graph, "imports", "file:svc/pong_mod.py", "file:svc/ping_pong.py")
    assert has_edge(graph, "calls", "func:svc/ping_pong.py::ping", "func:svc/pong_mod.py::pong")
    assert has_edge(graph, "calls", "func:svc/pong_mod.py::pong", "func:svc/ping_pong.py::ping")


def test_config_binding_field_to_key_and_reads(graph):
    f = "field:svc/settings.py::Cfg.redis_host"  # Cfg(redis_host=os.getenv("REDIS_HOST"))
    assert has_edge(graph, "reads_config", f, "cfg:REDIS_HOST")
    assert has_edge(graph, "declares_config", "class:svc/settings.py::Cfg", "cfg:REDIS_HOST")
    [(_, _, d)] = [e for e in edges(graph, "reads_config") if e[:2] == (RUN, "cfg:REDIS_HOST")]
    assert d["via"] == f and d["source"] == "settings" and d["confidence"] == 0.9
    assert d["provenance"].startswith("svc/app.py:")
    # pydantic env_prefix: Settings.log_level -> APP_LOG_LEVEL
    sf = "field:svc/settings.py::Settings.log_level"
    assert has_edge(graph, "reads_config", sf, "cfg:APP_LOG_LEVEL")
    assert has_edge(graph, "reads_config", RUN, "cfg:APP_LOG_LEVEL")
    # direct env reads and an imported module constant bound to an env key
    assert has_edge(graph, "reads_config", "func:svc/store.py::connect", "cfg:EXTRA_KEY")
    assert has_edge(graph, "reads_config", RUN, "cfg:LOG_X")
    assert has_edge(graph, "reads_config", "func:svc/settings.py::get_cfg", "cfg:DB_POOL")


def test_compose_services_env_runs_depends(graph):
    assert has_edge(graph, "service_env", "svc:api", "cfg:REDIS_HOST")
    assert has_edge(graph, "service_env", "svc:api", "cfg:EXTRA_KEY")  # env_file, names only
    assert has_edge(graph, "depends_on", "svc:api", "svc:cache")
    assert has_edge(graph, "service_runs", "svc:api", "file:svc/__main__.py")  # python -m svc
    [(_, _, d)] = [e for e in edges(graph, "service_env") if e[1] == "cfg:REDIS_HOST"]
    lines = (graph.repo / "compose.yaml").read_text().splitlines()
    want = next(i for i, ln in enumerate(lines, 1) if "REDIS_HOST:" in ln)
    assert d["source"] == "compose" and d["provenance"] == f"compose.yaml:{want}"


def test_compose_yaml_merge_keys_are_expanded(graph):
    assert has_edge(graph, "service_env", "svc:worker", "cfg:SHARED_KEY")  # <<: *base
    assert has_edge(graph, "service_runs", "svc:worker", "file:svc/__main__.py")


def test_tests_covers_by_call_and_type(graph):
    t1 = "test:svc/tests/test_app.py::test_run"
    t2 = "test:svc/tests/test_app.py::test_store_save"
    assert has_edge(graph, "tests_covers", t1, RUN)
    assert has_edge(graph, "tests_covers", t2, SAVE)
    assert not [e for e in edges(graph, "calls") if e[0].startswith("test:")]


def test_every_edge_has_source_provenance_and_a_reverse(graph):
    seen = set()
    for _u, _v, d in graph.nx.edges(data=True):
        assert d["source"] in SOURCES and d["provenance"] and 0 <= d["confidence"] <= 1
        assert d["weight"] > 0
        seen.add(d["type"])
    assert set(FORWARD_TYPES) <= seen and set(REVERSE_OF.values()) <= seen
    back = {e[:2] for e in edges(graph, "called_by", reverse=True)}
    assert all((v, u) in back for u, v, _ in edges(graph, "calls"))


def test_syntax_error_file_is_flagged_not_fatal(graph):
    assert "error" in graph.node("file:svc/broken.py")
    assert graph.stats["syntax_errors"] == 1


def test_deterministic(graph):
    g2 = build_graph(graph.repo, "fixture-sha", cache_dir=None)
    assert list(g2.nx.nodes) == list(graph.nx.nodes)
    assert list(g2.nx.edges(keys=True)) == list(graph.nx.edges(keys=True))
    assert g2.content_hash == graph.content_hash
