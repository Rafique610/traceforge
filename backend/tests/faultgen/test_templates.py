# ruff: noqa: E501
"""Template unit tests: patches apply cleanly, reverse exactly, gold spans match the changed lines."""

import pytest
from fg_paths import LAB

from traceforge.contracts.case_manifest import CaseManifest
from traceforge.faultgen import lab_tree
from traceforge.faultgen.generate import materialize
from traceforge.faultgen.model import build_case
from traceforge.faultgen.patching import PatchError, apply_patch
from traceforge.faultgen.seeds import seed_drafts
from traceforge.faultgen.templates import code, config


def _all_drafts():
    drafts = list(seed_drafts(LAB))
    drafts += [code.make(f"x-{s}", site=s, lab=LAB) for s in code.SITES]
    drafts += [config.make("x-port", field="redis_port", bad_value="6397", lab=LAB)]
    return drafts


@pytest.mark.parametrize("draft", _all_drafts(), ids=lambda d: d.case_id)
def test_patch_applies_reverses_and_spans_match(draft, tmp_path):
    built = build_case(draft, LAB)
    assert CaseManifest.model_validate(built.manifest.model_dump())
    tree = materialize(built.patch, tmp_path / "t", LAB)
    if not draft.edits:
        assert built.patch == ""
        return
    changed = [
        ln for ln in built.patch.splitlines() if ln.startswith("+") and not ln.startswith("+++")
    ]
    assert len(changed) == 1  # one line mutated
    for sym in built.manifest.gold_symbols:
        text = (tree / sym.path).read_text("utf-8").splitlines()
        assert changed[0][1:] in text[sym.start_line - 1 : sym.end_line]
    apply_patch(tree, built.patch, reverse=True)
    for rel in draft.edits:
        assert (tree / rel).read_bytes() == (LAB.parent / rel).read_bytes()


def test_patch_refuses_a_drifted_tree(builts, tmp_path):
    b = next(b for b in builts if b.manifest.case_id == "shop_api-002")
    tree = materialize("", tmp_path / "t", LAB)
    target = tree / next(iter(b.draft.edits))
    target.write_bytes(target.read_bytes().replace(b"Field(", b"Field( "))
    with pytest.raises(PatchError):
        apply_patch(tree, b.patch)


def test_seed_cases_cover_classes_formats_and_split(builts):
    ms = [b.manifest for b in builts]
    assert {m.cause_class for m in ms} == {
        "configuration",
        "application_code",
        "runtime_dependency",
        "insufficient_evidence",
    }
    assert len({m.log_format for m in ms}) >= 3
    assert {m.split for m in ms} == {"dev"}
    cfg = next(m for m in ms if m.cause_class == "configuration")
    assert cfg.distance >= 1 and cfg.gold_config_keys
    for m in ms:
        if m.cause_class in ("runtime_dependency", "insufficient_evidence"):
            assert not (m.gold_symbols or m.gold_config_keys or m.hidden_test_ids)
            assert m.distance is None


def test_generation_is_deterministic():
    a = [build_case(d, LAB).manifest for d in seed_drafts(LAB)]
    b = [build_case(d, LAB).manifest for d in seed_drafts(LAB)]
    assert a == b


def test_base_sha_tracks_content_not_caches(lab_copy):
    sha = lab_tree.base_sha(lab_copy)
    assert sha == lab_tree.base_sha(LAB)
    (lab_copy / "shop_api" / "app" / "__pycache__").mkdir()
    (lab_copy / "shop_api" / "app" / "__pycache__" / "x.pyc").write_bytes(b"1")
    assert lab_tree.base_sha(lab_copy) == sha
    (lab_copy / "shop_api" / "app" / "pricing.py").write_text("# changed\n")
    assert lab_tree.base_sha(lab_copy) != sha
