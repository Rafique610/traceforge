"""materialize_tree uses committed case data only: no generator run, datasets and lab untouched."""

import subprocess
from pathlib import Path

from traceforge.agent import lab_collect
from traceforge.faultgen import generate

REPO = Path(__file__).resolve().parents[3]


def _tracked_state() -> str:
    return subprocess.run(  # noqa: S603
        ["git", "-C", str(REPO), "status", "--porcelain", "--", "datasets", "lab"],  # noqa: S607
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_materialize_tree_is_deterministic_and_read_only(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("dataset generator / subprocess must not run")

    monkeypatch.setattr(generate, "main", boom)
    monkeypatch.setattr(lab_collect, "sh", boom)
    before = _tracked_state()
    a = lab_collect.materialize_tree("shop_api-005", tmp_path / "a")
    b = lab_collect.materialize_tree("shop_api-005", tmp_path / "b")
    assert _tracked_state() == before
    assert _files(a) == _files(b)
    pristine = (REPO / "lab/shop_api/app/settings.py").read_bytes()
    assert _files(a)["lab/shop_api/app/settings.py"] != pristine  # the mutation is applied


def test_bundle_valid_rejects_garbage(tmp_path):
    p = tmp_path / "shop_api-005.json"
    assert not lab_collect.bundle_valid(p, "shop_api-005")
    p.write_text("{}", "utf-8")
    assert not lab_collect.bundle_valid(p, "shop_api-005")


def test_evidence_key_changes_with_inputs_and_stale_bundles_are_not_reused(tmp_path, monkeypatch):
    from traceforge.agent import lab_collect as lc
    from traceforge.agent.real_sources import ManifestCaseSource

    repo_ds = lc.REPO / "datasets"
    case = ManifestCaseSource(repo_ds / "manifests/dev.json").get("shop_api-002")
    ds = tmp_path / "datasets"
    (ds / "cases" / case.case_id).mkdir(parents=True)
    for name in ("mutation.patch", "meta.json"):
        (ds / "cases" / case.case_id / name).write_bytes(
            (repo_ds / "cases" / case.case_id / name).read_bytes()
        )
    k1 = lc.evidence_key(case, ds)
    assert k1 == lc.evidence_key(case, ds)  # deterministic
    (ds / "cases" / case.case_id / "mutation.patch").write_text("changed", "utf-8")
    assert lc.evidence_key(case, ds) != k1  # a changed case invalidates its evidence

    monkeypatch.setattr(lc, "bundle_valid", lambda p, c: True)
    out = tmp_path / "ev" / "shop_api-002.json"
    out.parent.mkdir()
    out.write_text("{}", "utf-8")
    assert not lc.bundle_current(out, case.case_id, k1)  # no key file: unkeyed bundles are stale
    out.with_suffix(".key").write_text(k1, "utf-8")
    assert lc.bundle_current(out, case.case_id, k1)
    assert not lc.bundle_current(out, case.case_id, "0" * 64)  # collected from other inputs
