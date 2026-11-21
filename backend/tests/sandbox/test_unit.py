# ruff: noqa: E501
"""Unit tests (no Docker): parsing, redaction, isolation flags, path handling, error paths."""

from pathlib import Path

import pytest

from traceforge.contracts.test_run import TestRunRequest
from traceforge.sandbox import images, runner
from traceforge.sandbox.config import SandboxConfig
from traceforge.sandbox.report import parse_junit, redact, tail

JUNIT = """<testsuites><testsuite time="0.5">
<testcase classname="tests.test_a.TestX" name="test_y" file="tests/test_a.py"/>
<testcase classname="tests.test_a" name="test_z" file="tests/test_a.py"><failure message="x"/></testcase>
<testcase classname="" name="tests.test_bad" file="tests/test_bad.py"><error message="c"/></testcase>
<testcase classname="tests.test_a" name="test_s" file="tests/test_a.py"><skipped/></testcase>
</testsuite></testsuites>"""


def req(wt, suite="visible", case="case1", t=30):
    return TestRunRequest(case_id=case, worktree_path=str(wt), suite=suite, timeout_s=t)


def test_parse_junit_ids_and_outcomes():
    tests, secs = parse_junit(JUNIT)
    assert [(t.id, t.outcome) for t in tests] == [
        ("tests/test_a.py::TestX::test_y", "passed"),
        ("tests/test_a.py::test_z", "failed"),
        ("tests/test_bad.py", "error"),
        ("tests/test_a.py::test_s", "skipped"),
    ]
    assert secs == 0.5


def test_redaction_and_tail_cap():
    text = "x" * 9000 + " password=hunter2 sk-abcdefghijklmnopqrstuvwx ghp_" + "a" * 30
    out = tail(text, 4096)
    assert len(out) <= 4096
    assert "hunter2" not in out and "sk-abcdef" not in out and "ghp_a" not in out
    assert redact("API_KEY: abc123") == "[REDACTED]"
    # a secret straddling the cut is still fully removed (redact before slicing)
    assert "SECRETVALUE" not in tail("token=SECRETVALUE" + "y" * 4090, 4096)


def test_isolation_flags_asserted():
    a = runner.docker_run_args(SandboxConfig(), "n")
    joined = " ".join(a)
    for flag in (
        "--network none", "--read-only", "--cap-drop ALL", "--security-opt no-new-privileges",
        "--memory 512m", "--memory-swap 512m", "--cpus 1", "--pids-limit 128", "--user 10001:10001",
    ):  # fmt: skip
        assert flag in joined
    assert any(x.startswith("/tmp:rw") for x in a)
    assert "docker.sock" not in joined and "--privileged" not in a and "--env-file" not in a
    assert [a[i + 1] for i, x in enumerate(a) if x == "-e"] == [
        "HOME=/tmp", "PYTHONDONTWRITEBYTECODE=1", "PYTHONHASHSEED=0",
    ]  # fmt: skip


def test_resolve_dir_relative_and_escape(tmp_path: Path):
    (tmp_path / "repo" / "wt").mkdir(parents=True)
    assert runner.resolve_dir("wt", tmp_path / "repo", "w") == (tmp_path / "repo" / "wt").resolve()
    with pytest.raises(images.SandboxError):
        runner.resolve_dir("../", tmp_path / "repo", "w")
    with pytest.raises(images.SandboxError):
        runner.resolve_dir("wt", None, "w")
    with pytest.raises(images.SandboxError):
        runner.resolve_dir(str(tmp_path / "missing"), None, "w")


def test_errors_never_look_like_success(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    for r, kw in (
        (req(wt, case="../x"), {}),
        (req(wt, "hidden"), {}),  # no hidden_dir configured
        (req(tmp_path / "nope"), {}),
        (req(wt, "hidden"), {"hidden_dir": wt}),  # hidden dir overlapping worktree
    ):
        res = runner.run_tests(r, **kw)
        assert res.error and res.passed == 0 and not res.timed_out


def test_docker_unavailable_sets_error(tmp_path: Path, monkeypatch):
    def boom(*a, **k):
        raise images.SandboxError("docker image inspect failed: no daemon")

    monkeypatch.setattr(runner, "ensure_image", boom)
    (tmp_path / "wt").mkdir()
    res = runner.run_tests(req(tmp_path / "wt"))
    assert "no daemon" in (res.error or "") and res.passed == 0 and res.tests == []


def test_image_tag_is_stable_and_depends_on_requirements():
    a, b = SandboxConfig(), SandboxConfig(requirements="pytest==8.3.4 httpx==0.28.1")
    assert images.image_tag(a) == images.image_tag(SandboxConfig())
    assert images.image_tag(a) != images.image_tag(b)
