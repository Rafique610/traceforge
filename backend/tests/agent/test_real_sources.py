# ruff: noqa: E501
"""Unit tests for the real source adapters; `e2e`-marked tests need Docker/model and skip without."""

import shutil
from pathlib import Path

import pytest

from traceforge.agent.real_sources import HiddenLeakGuard, LabEvidenceSource, ManifestCaseSource

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "datasets/manifests/dev.json"
EVIDENCE = REPO / "runs/evidence"


def test_manifest_case_source_reads_dev_manifest():
    src = ManifestCaseSource(MANIFEST)
    assert src.get("shop_api-001").cause_class == "configuration"
    assert len(src.sha256) == 64
    with pytest.raises(KeyError):
        src.get("nope")


@pytest.mark.skipif(not (EVIDENCE / "shop_api-001.json").is_file(), reason="no saved evidence")
def test_lab_evidence_source_returns_saved_bundle_with_new_incident_id():
    case = ManifestCaseSource(MANIFEST).get("shop_api-001")
    b = LabEvidenceSource(EVIDENCE).collect("inc-x", case.service, case)
    assert b.incident_id == "inc-x" and b.items


def test_lab_evidence_source_missing_without_collector(tmp_path):
    case = ManifestCaseSource(MANIFEST).get("shop_api-001")
    with pytest.raises(FileNotFoundError):
        LabEvidenceSource(tmp_path).collect("i", case.service, case)


def test_hidden_leak_guard_blocks_hidden_names(tmp_path):
    d = tmp_path / "c1"
    d.mkdir()
    (d / "test_hidden_x.py").write_text("def test_secret_name():\n    assert 1\n")
    (d / "conftest.py").write_text("")
    g = HiddenLeakGuard(tmp_path, ["c1"])
    seen = []
    chat = g.wrap(lambda m, *a, **k: seen.append(m) or "ok")
    assert chat([{"role": "user", "content": "plain"}]) == "ok"
    with pytest.raises(AssertionError):
        chat([{"role": "user", "content": "see test_secret_name"}])
    assert "conftest.py" not in g.markers


@pytest.mark.e2e
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker missing")
def test_real_sandbox_adapter_constructs():
    from traceforge.agent.real_sources import make_sandbox_run_tests

    assert callable(make_sandbox_run_tests(REPO, REPO / "datasets"))
