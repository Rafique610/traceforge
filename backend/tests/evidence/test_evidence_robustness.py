# ruff: noqa: E501
"""Collector robustness: partial Docker data, unreadable settings, oversized log lines. Failures
are explicit evidence/warnings and never abort the collection. Fake Docker client, offline."""

import shutil
from pathlib import Path

from test_evidence_collector import CFG, FakeClient, FakeContainer

from traceforge.evidence import EvidenceCollector, EvidenceConfig, logs

REPO = Path(__file__).resolve().parents[3]


def _containers():
    return {
        "lab_db": FakeContainer("lab_db"),
        "lab_redis": FakeContainer("lab_redis"),
        "shop_api": FakeContainer("shop_api", log="INFO started\n"),
        "worker": FakeContainer("worker"),
    }


class FlakyClient(FakeClient):
    def __init__(self, by_service, fail_list=(), fail_all=False):
        super().__init__(by_service)
        self.fail_list, self.fail_all = set(fail_list), fail_all

    def list(self, all=True, filters=None):
        svc = next(x.split("=", 1)[1] for x in filters["label"] if "service=" in x)
        if self.fail_all or svc in self.fail_list:
            raise ConnectionError("proxy down")
        return super().list(all, filters)


def test_one_unreadable_container_is_reported_and_the_rest_is_kept():
    col = EvidenceCollector(
        CFG, FlakyClient(_containers(), fail_list=["lab_redis"])
    ).collect_detailed("i", "shop_api", None)
    blob = "\n".join(i.content for i in col.bundle.items)
    assert (
        "service lab_redis: container state unavailable (Docker read failed: ConnectionError)"
        in blob
    )
    assert "container traceforge-lab-lab_db-1: running" in blob  # others still collected
    assert any("lab_redis" in w for w in col.warnings)


def test_no_docker_at_all_still_yields_static_evidence_and_explicit_unavailable_items():
    col = EvidenceCollector(CFG, FlakyClient(_containers(), fail_all=True)).collect_detailed(
        "i", "shop_api", None
    )
    kinds = [i.kind for i in col.bundle.items]
    assert kinds.count("health") == 4 and "compose" in kinds and "config" in kinds
    assert all("unavailable" in i.content for i in col.bundle.items if i.kind == "health")
    assert not any(i.kind == "log" for i in col.bundle.items)


def test_a_log_read_failure_is_an_explicit_item_not_an_exception(monkeypatch):
    from traceforge.evidence import docker_read

    def boom(*a, **k):
        raise TimeoutError("slow")

    monkeypatch.setattr(docker_read, "read_logs", boom)
    col = EvidenceCollector(CFG, FakeClient(_containers())).collect_detailed("i", "shop_api", None)
    assert any(
        "logs unavailable (Docker read failed: TimeoutError)" in i.content for i in col.bundle.items
    )
    assert any("logs unavailable" in w for w in col.warnings)


def test_unparseable_settings_source_becomes_an_item_with_the_line(tmp_path, monkeypatch):
    from traceforge.evidence import collector

    (tmp_path / "lab/shop_api/app").mkdir(parents=True)
    shutil.copy(REPO / "lab/compose.yaml", tmp_path / "lab/compose.yaml")
    (tmp_path / "lab/shop_api/app/settings.py").write_text("class Settings:\n    x: int = (\n")
    monkeypatch.setattr(collector, "git_head", lambda cfg: "0" * 40)
    cfg = EvidenceConfig(repo_root=tmp_path, probes={})
    res = EvidenceCollector(cfg, FakeClient(_containers())).collect_detailed("i", "shop_api", None)
    items = [i for i in res.bundle.items if i.kind == "config" and i.path]
    assert len(items) == 1 and "SyntaxError" in items[0].content and items[0].line
    assert any("unreadable" in w for w in res.warnings)


def test_one_huge_log_line_does_not_erase_the_window():
    huge = "x" * 200_000
    lines, cut = logs.window(f"first\n{huge}\nlast ERROR boom", 400, 32 * 1024)
    assert cut and lines[0] == "first" and lines[-1] == "last ERROR boom"
    assert all(len(ln) < 2100 for ln in lines)


def test_probe_survives_malformed_http_replies(monkeypatch):
    import http.client

    from traceforge.evidence import collector

    def bad(*a, **k):
        raise http.client.BadStatusLine("garbage")

    monkeypatch.setattr(collector.urllib.request, "urlopen", bad)
    assert "unreachable (BadStatusLine)" in collector._probe("http://127.0.0.1:1/health", 0.1)
