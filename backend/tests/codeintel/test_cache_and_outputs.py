import json

from traceforge.codeintel import approx_tokens, build_graph, code_map, export_subgraph
from traceforge.codeintel.cli import main

RUN = "func:svc/app.py::run"


def test_cache_hit_and_incremental_rebuild(repo, tmp_path):
    cd = tmp_path / "cache"
    g1 = build_graph(repo, "sha1", cache_dir=cd)
    assert g1.stats["reparsed"] == g1.stats["python_files"] > 5
    assert list(cd.glob("sha1__*.json"))
    g2 = build_graph(repo, "sha1", cache_dir=cd)
    assert g2.stats["reparsed"] == 0 and g2.content_hash == g1.content_hash
    assert list(g2.nx.edges(keys=True)) == list(g1.nx.edges(keys=True))
    # edit one file: only it is re-parsed and the graph reflects the change
    f = repo / "svc" / "store.py"
    f.write_text(f.read_text() + "\n\ndef added():\n    return helper()\n")
    g3 = build_graph(repo, "sha1", cache_dir=cd)
    assert g3.stats["reparsed"] == 1 and g3.content_hash != g1.content_hash
    assert any(
        d["type"] == "calls" and (u, v) == ("func:svc/store.py::added", "func:svc/store.py::helper")
        for u, v, d in g3.nx.edges(data=True)
    )
    # a new SHA seeds from the latest cache of the same repo: unchanged files are reused
    assert build_graph(repo, "sha2", cache_dir=cd).stats["reparsed"] == 0
    f.unlink()  # deletion drops the file's nodes
    g5 = build_graph(repo, "sha2", cache_dir=cd)
    assert "file:svc/store.py" not in g5 and g5.stats["reparsed"] == 0
    fresh = build_graph(repo, "sha2", cache_dir=None)  # incremental == from scratch
    assert list(fresh.nx.edges(keys=True)) == list(g5.nx.edges(keys=True))


def test_corrupt_cache_is_ignored(repo, tmp_path):
    cd = tmp_path / "c"
    build_graph(repo, "s", cache_dir=cd)
    for p in cd.glob("*.json"):
        p.write_text("{not json")
    g = build_graph(repo, "s", cache_dir=cd)
    assert g.stats["reparsed"] == g.stats["python_files"]


def test_code_map_has_signatures_and_no_bodies(graph):
    m = code_map(graph)
    assert "def save(self, item=None) -> bool" in m
    assert "  class SubStore(Store)\n    def again(self)" in m
    assert "return" not in m and "os.environ" not in m
    assert "REDIS_HOST" in m and "services: api, cache" in m
    assert "tests: test_run, test_store_save" in m
    assert m == code_map(graph) and 0 < approx_tokens(m) < len(m)


def test_export_json_and_mermaid(graph):
    d = json.loads(export_subgraph(graph, [RUN], hops=1))
    ids = {n["id"] for n in d["nodes"]}
    assert RUN in ids and "cfg:REDIS_HOST" in ids
    e = [x for x in d["edges"] if x["target"] == "cfg:REDIS_HOST" and x["source"] == RUN][0]
    assert e["type"] == "reads_config" and e["provenance"].startswith("svc/app.py:")
    assert all({"type", "provenance", "confidence", "source_kind"} <= set(x) for x in d["edges"])
    mm = export_subgraph(graph, ["func:svc/app.py::dispatch"], 1, "mermaid")
    assert mm.startswith("flowchart LR") and "-.->" in mm and "unknown: handlers[name]" in mm
    assert "calls @ svc/app.py:" in mm
    capped = json.loads(export_subgraph(graph, [RUN], hops=2, max_nodes=3, include_unknown=False))
    assert len(capped["nodes"]) == 3


def test_cli_self_check(capsys, repo):
    main([str(repo), "--no-cache", "--distance", RUN, "cfg:REDIS_HOST"])
    out = capsys.readouterr().out
    assert '"nodes"' in out and "unknown_call_edges" in out and "build:" in out
    assert "distance: 1" in out
