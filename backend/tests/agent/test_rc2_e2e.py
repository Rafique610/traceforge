"""RC2 opt-in wiring in agent/e2e.py: rc1 default unchanged, rc2 metadata, mismatch refused."""

import pytest

from traceforge.agent import e2e
from traceforge.agent.rc2.version import RC1_FINGERPRINT, VersionLabelError, select_chat_fn


def test_default_path_is_rc1_identity():
    fn = object()
    assert select_chat_fn("rc1", fn) is fn  # chat fn identical: RC1 path untouched
    lab = e2e._rc_label("rc1")
    assert lab == {"code_version": "rc1", "code_fingerprint": RC1_FINGERPRINT}


def test_rc2_meta_recorded_with_rc2_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(e2e, "RC2_FP_FILE", tmp_path / "rc2-fingerprint.txt")
    lab = e2e._rc_label("rc2")
    assert lab["code_version"] == "rc2"
    assert lab["code_fingerprint"] != RC1_FINGERPRINT
    assert (tmp_path / "rc2-fingerprint.txt").read_text("utf-8") == lab["code_fingerprint"]


def test_label_fingerprint_mismatch_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(e2e, "rc2_fingerprint", lambda: {"sha256": RC1_FINGERPRINT})
    monkeypatch.setattr(e2e, "RC2_FP_FILE", tmp_path / "fp.txt")
    with pytest.raises(VersionLabelError):
        e2e._rc_label("rc2")
    monkeypatch.setattr(e2e, "code_fingerprint", lambda: {"sha256": "0" * 64})
    with pytest.raises(VersionLabelError):
        e2e._rc_label("rc1")
