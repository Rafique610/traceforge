# ruff: noqa: E501
"""Default off leaves the injected runner and the RC1 label untouched; labels stay RC2-family."""

from contextlib import ExitStack

import pytest

from traceforge.agent import e2e
from traceforge.agent.rc2.version import RC1_FINGERPRINT, VersionLabelError, run_label
from traceforge.config import Settings
from traceforge.evaluation.fingerprint import code_fingerprint
from traceforge.regression import wire_regression


def test_off_returns_the_original_runner_object():
    base = object()
    with ExitStack() as stack:
        out = wire_regression(
            base,
            layer="off",
            repo_path=".",
            base_sha="x",
            selected=None,
            condition="G1",
            stack=stack,
        )  # type: ignore[arg-type]
    assert out is base


def test_rc1_fingerprint_frozen_and_labels_unchanged_by_default():
    assert code_fingerprint()["sha256"] == RC1_FINGERPRINT
    assert e2e._rc_label("rc1") == {"code_version": "rc1", "code_fingerprint": RC1_FINGERPRINT}
    assert run_label("rc1", RC1_FINGERPRINT, "off") == run_label("rc1", RC1_FINGERPRINT)


def test_regression_run_is_rc2_family_and_never_rc1(tmp_path, monkeypatch):
    monkeypatch.setattr(e2e, "RC2_FP_FILE", tmp_path / "fp.txt")
    lab = e2e._rc_label("rc2", "s15")
    assert lab["regression_layer"] == "s15" and lab["code_version"] == "rc2"
    assert lab["code_fingerprint"] != RC1_FINGERPRINT
    with pytest.raises(VersionLabelError):
        run_label("rc1", RC1_FINGERPRINT, "graph")
    with pytest.raises(VersionLabelError):
        run_label("rc2", "0" * 64, "bogus")


def test_cli_refuses_regression_without_rc2():
    with pytest.raises(SystemExit):
        e2e.main(["--case", "x", "--condition", "G1", "--regression", "graph"])


def test_settings_investigate_regression_default_off_and_validated():
    assert Settings().investigate_regression == "off"
    assert Settings(investigate_regression="s15").investigate_regression == "s15"
    with pytest.raises(ValueError):
        Settings(investigate_regression="bogus")
